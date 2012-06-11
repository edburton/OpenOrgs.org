import datetime
from google.appengine.ext import db

class User(db.Model):
    email = db.Email(required=True)
    contacts = db.ListProperty(db.ReferenceProperty(User))
    events = db.ListProperty(db.ReferenceProperty(Event))
    
class Event(db.Model):
    title = db.str(required=True)
    description = db.Text()

class EventInstance(db.Model):
    date = datetime.date