#### Author: ampourgh | Version: 1.0.0 | Last Modified: 7/29/2017

# Project 4 — Item Catalog

## Getting Started

### Prerequisites
Project functions with the following:
* Git (version 2.13.0.windows.1) - command line used
* Python (3.61) - used to run Python's code
* Vagrant (1.9.5) - Used for displaying and querying database. Once installed from vagrantup's website, use vagrant --version in git to check if vagrant is running
* Oracle's VM VirtualBox Manager (5.1.22) - for running vagrant]
* Python files import Flask (0.12.2), SQLalchemy, oauth2client, JSON, requests, and httplib frameworks and libraries in Python

### Files included
* Vagrantfile - used for running vagrant and VirtualBox
* database_setup.py - sets up table classes using SQLalchemy, with User, Catalog and MenuItem tables, each with their own variables and foreign keys connected with each other
* project.py - the Flask and oauthclient section that establishes how the tables function within each webpage
* client_secrets.json - contains a table of authorization information in order to use gmail's login
* static folder - which contains the img and css folders
* templates - contains the html templates, which function with Jinja2 to do basic Python loops and conditions, along with connecting with project.py

### Installing
1. Fork the catalog folder.
2. Copy the link of the fork.
3. In Git, use the clone command as so: git clone <forked url> <folder name>

### Running tests
1. Through Git Bash, navigate to the Vagrantfile which is inside what the forked folder was called.
2. 'Vagrant Up' to get VM VirtualBox running.
3. 'Vagrant SSH' to log in.
4. Use the command 'cd /vagrant' to move out of home/vagrant to the vagrant folder that holds the files
5. Install pip in order to install the requirements of the Catalog app.
```
sudo apt-get -y install python3-pip python3-
```
7. Pip install all the imported frameworks and libraries in project.py and database_setup.p. Requirements.txt includes Flask, SQLAlchemy, psycopg2, requests, oauth2client and httplib2.
```
sudo pip3 install -r requirements.tx
```
8. Compile database_setup.py to set up archive.db, which contains the database information.
```
python database_setup.py
```
9. Compile project.py to get webpage running (which can be found at localhost:5000)
```
python project.py
```

#### How to modify database_setup.py

The webpage has 3 table classes, 2 of which are serialized to be read as a JSON file. The name of function for the example below is className, with the table name as class_name, with the variable id acting as the unique primary key. Additional variables can be added as integors, strings, datetime, etc. Foreign key and relationship keys can also be added to connect the tables, making information retrieval viable.

```python
class className(Base):
    __tablename__ = 'class_name'

    id = Column(Integer, primary_key=True)

        @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
          'id': self.id,
        }
```

This is the section where archive.db is named and created when running database_setup.py.
```python
engine = create_engine('sqlite:///archive.db')
```

#### How to modify project.py

There are a number of functions in project.py, either for the login, rendering the webpage with the database information, or storing/modifying information with the POST CRUD functionality. The basic building block of a web rendering function is below. The first line routes to the extension localhost will store the webpage, with the function name being how webpages are linked. The render template stores the webpage name, which will be located in templates, with variables used on the page coming after.

```python
@app.route('/')
def webpageFunctionName():

  return render_template('.html', variable=variable)
```

#### How to modify project.py

The function can be as so in an html page, directing to project.py, along with variables drawn from the page. Variables are usually inherited in cases where the former webpage has useful information to creating the next page.

```python
<a href='{{url_for('webpageFunctionName', variable = variable) }}'>
```

### Acknowledgments
Used tutorials from Udacity, w3schools, Treehouse and MDN for putting together the Flask code and CSS structure; including table, footer and dropdown.
