from flask import (Flask, render_template, request, redirect,
                   jsonify, url_for, flash)
from datetime import date, datetime
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Catalog, MenuItem, User

# import for creating anti-forgery state token
# login session works like a dictionary; store values in it
from flask import session as login_session
# used to create a pusedo-random string for each login session
import random, string

# from clientsecrets JSON file creates a flow object
# where client ID is stored
from oauth2client.client import flow_from_clientsecrets
# if we recieved an error trying to exchange auth code for access token
# use this method to catch it
from oauth2client.client import FlowExchangeError
# a comprehensive client library in Python
import httplib2
# provides an API for converting in memory Python objects
# to a serialized representation; known as JSON
import json
# converts return value from a function into a real
# response object that can be sent off to client
from flask import make_response
# an apache2 http library written to Python
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Archive"


# Connect to Database and create database session
engine = create_engine('sqlite:////archive.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps("""Current user is already
                                             connected."""), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += """ " style = "width: 300px;
                             height: 300px;
                             border-radius: 150px;
                             -webkit-border-radius: 150px;
                             -moz-border-radius: 150px;"> """
    flash("you are now logged in as %s" % login_session['username'])
    print("done!")
    return output


# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    credentials = login_session.get('credentials')
    if credentials is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view Catalog Information
@app.route('/catalog/<catalog_name>/JSON')
@app.route('/catalog/<catalog_name>/menu/JSON')
def catalogMenuJSON(catalog_name):
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    items = session.query(MenuItem).filter_by(
        name=catalog_name).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/catalog/<catalog_name>/<menu_name>/JSON')
def menuItemJSON(catalog_name, menu_name):
    Menu_Item = session.query(MenuItem).filter_by(name=menu_name).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


@app.route('/catalog/JSON')
def catalogsJSON():
    catalogs = session.query(Catalog).all()
    return jsonify(catalogs=[r.serialize for r in catalogs])


# Show all catalogs
@app.route('/')
@app.route('/catalog/')
def showCatalogs():
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    items = session.query(MenuItem).order_by(desc(
                          MenuItem.created_date)).limit(5).all()
    if 'username' not in login_session:
        return render_template('publiccatalogs.html',
                               catalogs=catalogs, items=items)
    else:
        return render_template('catalogs.html', catalogs=catalogs, items=items)


# User profile
@app.route('/user/')
def showUser():
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    items = session.query(MenuItem).order_by(desc(
                          MenuItem.created_date)).limit(20).all()
    if 'username' not in login_session:
        return render_template('publiccatalogs.html',
                               catalogs=catalogs, items=items)
    else:
        return render_template('user.html', catalogs=catalogs, items=items)


# Create a new catalog
@app.route('/catalog/new/', methods=['GET', 'POST'])
def newCatalog():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newCatalog = Catalog(
            name=request.form['name'], user_id=login_session['user_id'])
        session.add(newCatalog)
        flash('New Catalog %s Successfully Created' % newCatalog.name)
        session.commit()
        return redirect(url_for('showCatalogs'))
    else:
        return render_template('newCatalog.html')


# Edit a catalog
@app.route('/catalog/<catalog_name>/edit/', methods=['GET', 'POST'])
def editCatalog(catalog_name):
    editedCatalog = session.query(
        Catalog).filter_by(name=catalog_name).one()
    if 'username' not in login_session:
        return redirect('/login')
    if editedCatalog.user_id != login_session['user_id']:
        return """
        <script>
        function myFunction() {alert(
        'You are not authorized to edit this catalog.
        Please create your own catalog in order to edit.');}
        </script><body onload='myFunction()''>
        """
    if request.method == 'POST':
        if request.form['name']:
            editedCatalog.name = request.form['name']
            flash('Catalog Successfully Edited %s' % editedCatalog.name)
            return redirect(url_for('showCatalogs'))
    else:
        return render_template('editCatalog.html', catalog=editedCatalog)


# Delete a catalog
@app.route('/catalog/<catalog_name>/delete/', methods=['GET', 'POST'])
def deleteCatalog(catalog_name):
    catalogToDelete = session.query(
        Catalog).filter_by(name=catalog_name).one()
    if 'username' not in login_session:
        return redirect('/login')
    if catalogToDelete.user_id != login_session['user_id']:
        return """<script>
        function myFunction() {alert(
        'You are not authorized to delete this catalog.
        Please create your own catalog in order to delete.');}
        </script><body onload='myFunction()''>"""
    if request.method == 'POST':
        session.delete(catalogToDelete)
        flash('%s Successfully Deleted' % catalogToDelete.name)
        session.commit()
        return redirect(url_for('showCatalogs'))
    else:
        return render_template('deleteCatalog.html', catalog=catalogToDelete)


# Show a catalog menu

@app.route('/catalog/<catalog_name>/')
@app.route('/catalog/<catalog_name>/menu/')
def showMenu(catalog_name):
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    # name = session.query(User.name).filter_by(id=User_id).one()
    creator = getUserInfo(catalog.user_id)
    items = session.query(MenuItem).filter_by(
        catalog_id=catalog.id).all()
    menu_item = session.query(MenuItem).filter_by(id=MenuItem.id)
    if 'username' not in login_session:
        return render_template('guestmenu.html', items=items, catalog=catalog,
                               creator=creator, catalogs=catalogs,
                               menu_item=menu_item)
    if creator.id != login_session['user_id']:
        return render_template('publicmenu.html', items=items, catalog=catalog,
                               creator=creator, catalogs=catalogs,
                               menu_item=menu_item)
    else:
        return render_template('menu.html', items=items, catalog=catalog,
                               creator=creator, catalogs=catalogs,
                               menu_item=menu_item)


@app.route('/catalog/<catalog_name>/<menu_name>/description',
           methods=['GET', 'POST'])
def itemDescription(catalog_name, menu_name):
    item = session.query(MenuItem).filter_by(name=menu_name).one()
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    return render_template('description.html', catalog=catalog, item=item)


# Create a new menu item
@app.route('/catalog/menu/new/', methods=['GET', 'POST'])
def newMenuItem():
    if 'username' not in login_session:
        return redirect('/login')
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    if request.method == 'POST':
        for catalog in catalogs:
            if catalog.id == request.form['catalog_choice']:
                return catalog
        if login_session['user_id'] != catalog.user_id:
            flash("""You are not authorized to add menu items to this archive.
                     Please create your own archive in order to add items.""")
            return redirect('/login', code=302)
        else:
            newItem = MenuItem(name=request.form['name'],
                               description=request.form['description'],
                               price=request.form['price'],
                               catalog_id=request.form['catalog_choice'],
                               user_id=catalog.user_id)
            session.add(newItem)
            session.commit()
            flash('New Menu %s Item Successfully Created' % (newItem.name))
            return redirect(url_for('showMenu',
                                    catalog_name=newItem.catalog.name))
    else:
        return render_template('newmenuitem.html', catalogs=catalogs)

# Edit a menu item


@app.route('/catalog/<catalog_name>/<menu_name>/edit', methods=['GET', 'POST'])
def editMenuItem(catalog_name, menu_name):
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(MenuItem).filter_by(name=menu_name).one()
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    catalogs = session.query(Catalog).order_by(asc(Catalog.name))
    if login_session['user_id'] != catalog.user_id:
        return """<script>
        function myFunction() {alert(
        'You are not authorized to edit menu items to this catalog.
        Please create your own catalog in order to edit items.');}
        </script><body onload='myFunction()''>"""
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['catalog_choice']:
            editedItem.catalog_id = request.form['catalog_choice']
        session.add(editedItem)
        session.commit()
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', catalog_name=catalog_name))
    else:
        return render_template('editmenuitem.html', catalog_name=catalog_name,
                               menu_name=menu_name, item=editedItem,
                               catalogs=catalogs)


# Delete a menu item
@app.route('/catalog/<catalog_name>/<menu_name>/delete',
           methods=['GET', 'POST'])
def deleteMenuItem(catalog_name, menu_name):
    if 'username' not in login_session:
        return redirect('/login')
    catalog = session.query(Catalog).filter_by(name=catalog_name).one()
    itemToDelete = session.query(MenuItem).filter_by(name=menu_name).one()
    if login_session['user_id'] != catalog.user_id:
        return """<script>
                function myFunction() {alert(
                'You are not authorized to delete menu items to this catalog.
                Please create your own catalog in order to delete items.');}
                </script><body onload='myFunction()''>"""
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', catalog_name=catalog_name))
    else:
        return render_template('deleteMenuItem.html', item=itemToDelete)


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']

        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showCatalogs'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showCatalogs'))


if __name__ == '__main__':
    app.run()
