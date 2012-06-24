import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import logging

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from webapp2_extras import sessions

######################MODEL##########################

class Contact(db.Model):
    email = db.EmailProperty()
    contacts = db.ListProperty(db.Key)
    
class Event(db.Model):
    title = db.TextProperty()
    description = db.TextProperty()
    invitation = db.TextProperty()
    dates = db.ListProperty(db.Key)

class Date(db.Model):
    date = db.DateTimeProperty()
    note = db.TextProperty()
    
################CONTROLLER###########################   

class BaseHandler(webapp2.RequestHandler):
    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session() 


def base_dictionary(self):
    dictionary = { }
    dictionary['site_name'] = self.app.config.get('site_name')
    dictionary['site_slogan'] = self.app.config.get('site_slogan')
    if users.get_current_user():
        dictionary['log_in_or_out_url'] = users.create_logout_url(self.request.uri)
        dictionary['log_in_or_out_text'] = 'logout'
        dictionary['user_email'] = users.get_current_user().email()
    else:
         dictionary['log_in_or_out_url'] = users.create_login_url(self.request.uri)
         dictionary['log_in_or_out_text'] = 'login'
    return dictionary

def return_current_contact(self):
    if (users.get_current_user()):
        email = users.get_current_user().email();
        if email:
            que = db.Query(Contact)
            que = que.filter('email =', email)
            contact_s = que.fetch(limit=1)
            if len(contact_s):
                return contact_s[0]
            else:
                contact = Contact(email=email)
                contact.put()
                return contact
        
def return_current_contacts_events(self):
    contact = return_current_contact(self)
    if contact:
        que = db.Query(Event)
        que = que.ancestor(contact.key())
        events_s = que.fetch(limit=None)
        if len(events_s):
            return events_s
        
        

class MainPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())

        temp = os.path.join(os.path.dirname(__file__), 'templates/index.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)

class LoginPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())

        temp = os.path.join(os.path.dirname(__file__), 'templates/login.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)

class ManageEventsPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())
        events = return_current_contacts_events(self)
        if events:
            template_values['events'] = events;
        temp = os.path.join(os.path.dirname(__file__), 'templates/manageevents.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
        
    def post(self):
        delete = self.request.get('delete')
        if delete:
            event = db.get(delete)
            que = db.Query(Date)
            que = que.ancestor(event.key())
            dates = que.fetch(limit=None)
            for date in dates:
                date.delete();
            event.delete()
        else:
            edit = self.request.get('edit')
            if edit:
                self.redirect("/events/add?edit=" + edit)
                return
        self.redirect("/events/manage")
        

class AddEventPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        template_values = dict(template_values.items() + base_dictionary(self).items())
        edit = self.request.get('edit')
        if edit:
            event = db.get(edit)
            template_values['event'] = event
            que = db.Query(Date)
            que = que.ancestor(event.key())
            dates = que.fetch(limit=None)
            template_values['dates'] = dates
        temp = os.path.join(os.path.dirname(__file__), 'templates/addevent.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
        
    def post(self):
        contact = return_current_contact(self)
        title = self.request.get('title')
        description = self.request.get('description')
        invitation = self.request.get('invitation')
        newdate = self.request.get('newdate')
        newnote = self.request.get('newnote')
        addnewdate = self.request.get('addnewdate')
        deletedate = self.request.get('deletedate')
        if deletedate:
            date = db.get(deletedate)
            date.delete()
        edit = self.request.get('edit')
        if edit:
            event = db.get(edit)
        else:
            event = Event(parent=contact)
        event.title = title.strip()
        event.description = description.strip()
        event.invitation = invitation.strip()
        event.put()
        if newdate:
            date = Date(parent=event)
            date.date = datetime.datetime.strptime(newdate, "%d/%m/%Y %H:%M")
            date.note = newnote.strip()
            date.put()
        if addnewdate:
            edit = str(event.key())
            self.redirect("/events/add?edit=" + edit)
        else:
            self.redirect("/events/manage")

        
class ContactsPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())

        temp = os.path.join(os.path.dirname(__file__), 'templates/contacts.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
        
class AddContactsPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())

        temp = os.path.join(os.path.dirname(__file__), 'templates/addcontacts.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)

################INITIALIZE###########################

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

config = {'site_name' : 'OpenOrgs.org',
          'site_slogan' : 'for getting together whenever forever' }
config['webapp2_extras.sessions'] = {
    'secret_key': 'OpenOrgs',
}

routes = [('/', MainPage),
                               ('/login', LoginPage),
                               ('/events/manage', ManageEventsPage),
                               ('/events/add', AddEventPage),
                               ('/contacts', ContactsPage),
                               ('/contacts/add', AddContactsPage)]

app = webapp2.WSGIApplication(routes=routes,
                              config=config,
                              debug=True)
