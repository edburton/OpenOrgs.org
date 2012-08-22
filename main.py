import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import logging
import time
import calendar
import pickle

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from webapp2_extras import sessions

######################MODEL##########################

class Contact(db.Model):
    id = db.StringProperty();
    email = db.EmailProperty()
    confirmedContacts = db.ListProperty(db.Key)
    incomingContacts = db.ListProperty(db.Key)
    outgoingContacts = db.ListProperty(db.Key)
    
    
class Event(db.Model):
    title = db.TextProperty()
    description = db.TextProperty()
    invitation = db.TextProperty()
    ticket = db.TextProperty()
    minCapacity = db.IntegerProperty()
    maxCapacity = db.IntegerProperty()

class Date(db.Model):
    date = db.DateTimeProperty()
    confirmed = db.BooleanProperty()
    cannotAttend = db.ListProperty(db.Key)
    canAttend = db.ListProperty(db.Key)
    willAttend = db.ListProperty(db.Key)

class Dictionary(db.Model):
    entries = db.ListProperty(db.Key)
    
class DictionaryEntry(db.Model):
    name = db.StringProperty();
    value = db.TextProperty()
    
    
################CONTROLLER########################### 


class EventDates:
    def __init__(self, event, dates):
        self.event = event
        self.dates = dates
        
class EventDateState:
    def __init__(self, event, date, state, available='unknown', alert='orange'):
        self.event = event
        self.date = date
        self.state = state
        self.available = available
        self.alert = alert
        
class DateState:
    suggestion = 'suggestion'
    invitation = 'invitation'
    ticket = 'ticket'
    unconfirmed = 'unconfirmed'
    confirmed = 'confirmed'
    


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
    user = users.get_current_user()
    if user:
        dictionary['log_in_or_out_url'] = users.create_logout_url(self.request.uri)
        dictionary['log_in_or_out_text'] = 'logout'
        dictionary['user_email'] = (user.email()).lower()
        if users.is_current_user_admin():
            dictionary['admin'] = 'true'
        contact = return_current_contact(self)
        requests = len(contact.incomingContacts);
        eventdatestates = return_all_contact_and_contacts_eventdatestates(self)
        event_alerts = 0;
        for eventdatestate in eventdatestates:
            if eventdatestate.alert == 'red':
                event_alerts = event_alerts + 1
        if event_alerts > 0:
            dictionary['event_alerts'] = event_alerts
        if requests:
            dictionary['contact_requests'] = requests
    else:
         dictionary['log_in_or_out_url'] = users.create_login_url(self.request.uri)
         dictionary['log_in_or_out_text'] = 'login'
    return dictionary

def return_contact_for_email(self, email):
    if email:
        email = email.lower()
        que = db.Query(Contact)
        que.filter('email =', email)
        contact_s = que.fetch(limit=1)
        if len(contact_s):
            contact = contact_s[0];
            contact_s[0].email = email #force returned email to be lowercase
            return contact_s[0]
        else:
            contact = Contact(email=email)
            contact.put()
            return contact

def return_current_contact(self):
    if (users.get_current_user()):
        id = users.get_current_user().user_id();
        email = (users.get_current_user().email()).lower();
        if id:
            que = db.Query(Contact)
            que.filter('id =', id)
            contact_s = que.fetch(limit=1)
            if len(contact_s):
                contact = contact_s[0]
                if contact.email != email:
                    contact.email = email
                    contact.put();
                return contact
            elif email:
                que = db.Query(Contact)
                que.filter('email =', email)
                contact_s = que.fetch(limit=1)
                if len(contact_s):
                    contact = contact_s[0]
                    contact.id = id;
                    contact.put();
                    return contact
                new_contact = Contact(email=email, id=id)
                new_contact.put()
                return new_contact

def return_contact(self, key):
    if key:
       return db.get(key)

def return_events_for_contact(self, key):
    if key:
        que = db.Query(Event)
        que.ancestor(key)
        events_s = que.fetch(limit=None)
        if len(events_s):
            return events_s
        
def return_current_contacts_events(self):
    contact = return_current_contact(self)
    if contact:
        return return_events_for_contact(self, contact.key())

def return_all_contact_and_contacts_eventdatestates(self):
    eventdatestates = []
    contact = return_current_contact(self)
    if contact:
        event_s = return_events_for_contact(self, contact.key())
        if event_s:
            for event in event_s:
                que = db.Query(Date)
                que.ancestor(event.key())
                dates = que.fetch(limit=None)
                for date in dates:
                    state = DateState.unconfirmed
                    alert = 'orange'
                    if date.confirmed:
                        state = DateState.confirmed
                        alert = 'green'
                    eventdatestate = EventDateState(event, date, state, '', alert)
                    eventdatestates.append(eventdatestate)           
        if contact.confirmedContacts:
            for confirmedContact in contact.confirmedContacts:
                event_s = return_events_for_contact(self, confirmedContact)
                if event_s:
                    for event in event_s:
                        que = db.Query(Date)
                        que.ancestor(event.key())
                        dates = que.fetch(limit=None)
                        for date in dates:
                            state = DateState.suggestion
                            available = 'unknown'
                            alert = 'red'
                            if date.confirmed:
                                if contact.key() in date.willAttend:
                                    state = DateState.ticket
                                    alert = 'green'
                                else:
                                    state = DateState.invitation
                            else:
                                if contact.key() in date.canAttend:
                                    available = 'available'
                                    alert = 'orange'
                                if contact.key() in date.cannotAttend:
                                    available = 'unavailable'
                                    alert = 'orange'
                            eventdatestates.append(EventDateState(event, date, state, available, alert)) 
    return eventdatestates
        
    
        
class MainPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        template_values = dict(template_values.items() + base_dictionary(self).items())
        eventdatestates = return_all_contact_and_contacts_eventdatestates(self)
        if eventdatestates:
            template_values['eventdatestates'] = sorted(eventdatestates, key=lambda d: d.date.date)
        temp = os.path.join(os.path.dirname(__file__), 'templates/events.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
    def post(self):
        thisContact = return_current_contact(self)
        available = self.request.get('available')
        confirm = self.request.get('confirm')
        unconfirm = self.request.get('unconfirm')
        accept = self.request.get('accept')
        cancel = self.request.get('cancel')
        if confirm:
            date = db.get(confirm)
            date.confirmed = True;
            date.put()
        if unconfirm:
            date = db.get(unconfirm)
            date.confirmed = False;
            date.put()
        if accept:
            date = db.get(accept)
            date.willAttend.append(thisContact.key())
            date.put()
        if cancel:
            date = db.get(cancel)
            date.willAttend.remove(thisContact.key())
            date.put()
        eventdatestates = return_all_contact_and_contacts_eventdatestates(self)
        for eventdatestate in eventdatestates:
            name = str(eventdatestate.date.key()) + '_available'
            value = self.request.get(name)
            if value == 'available' and not (thisContact.key() in eventdatestate.date.canAttend):
                logging.info('!!!!!!!!!!!!!' + name + ' is now available ' + value)
                eventdatestate.date.canAttend.append(thisContact.key())
                if thisContact.key() in eventdatestate.date.cannotAttend:
                    eventdatestate.date.cannotAttend.remove(thisContact.key())
                eventdatestate.date.put()
            elif value == 'unavailable' and not (thisContact.key() in eventdatestate.date.cannotAttend):
                logging.info('!!!!!!!!!!!!!' + name + ' is now unnavailable ' + value)
                eventdatestate.date.cannotAttend.append(thisContact.key())
                if thisContact.key() in eventdatestate.date.canAttend:
                    eventdatestate.date.canAttend.remove(thisContact.key())
                eventdatestate.date.put()
            
        self.redirect("/")
        
class LoginPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())

        temp = os.path.join(os.path.dirname(__file__), 'templates/login.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
        
class AdminPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        template_values = dict(template_values.items() + base_dictionary(self).items())
        temp = os.path.join(os.path.dirname(__file__), 'templates/admin.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)

class ManageEventsPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        template_values = dict(template_values.items() + base_dictionary(self).items())
        events = return_current_contacts_events(self)
        eventsdates = []
        if events:
            for event in events:
                que = db.Query(Date)
                que.ancestor(event.key())
                que.order('date')
                dates = que.fetch(limit=None)
                eventdates = EventDates(event, dates)
                eventsdates.append(eventdates)
            template_values['eventsdates'] = eventsdates;
                
        temp = os.path.join(os.path.dirname(__file__), 'templates/manageevents.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
        
    def post(self):
        delete = self.request.get('delete')
        if delete:
            event = db.get(delete)
            que = db.Query(Date)
            que.ancestor(event.key())
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
            que.ancestor(event.key())
            que.order('date')
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
        ticket = self.request.get('ticket')
        newdate = self.request.get('newdate')
        addnewdate = self.request.get('addnewdate')
        deletethisdate = self.request.get('deletethisdate')
        if deletethisdate:
            date = db.get(deletethisdate)
            date.delete()
        edit = self.request.get('edit')
        if edit:
            event = db.get(edit)
        else:
            event = Event(parent=contact)
        event.title = title.strip()
        event.description = description.strip()
        event.invitation = invitation.strip()
        event.ticket = ticket.strip()
        event.put()
        if newdate:
            date = Date(parent=event)
            date.date = datetime.datetime.strptime(newdate, "%d/%m/%Y %H:%M")
            date.put()
        if addnewdate or deletethisdate:
            edit = str(event.key())
            self.redirect("/events/add?edit=" + edit)
        else:
            self.redirect("/events/manage")

        
class ContactsPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        template_values = dict(template_values.items() + base_dictionary(self).items())
        contact = return_current_contact(self)
        if contact:
            if contact.confirmedContacts:
                confirmedContacts = []
                for confirmedContact in contact.confirmedContacts:
                    confirmedContacts.append(db.get(confirmedContact))
                template_values['confirmedContacts'] = confirmedContacts;
            if contact.incomingContacts:
                incomingContacts = []
                for incomingContact in contact.incomingContacts:
                    incomingContacts.append(db.get(incomingContact))
                template_values['incomingContacts'] = incomingContacts;
            if contact.outgoingContacts:
                outgoingContacts = []
                for outgoingContact in contact.outgoingContacts:
                    outgoingContacts.append(db.get(outgoingContact))
                template_values['outgoingContacts'] = outgoingContacts;
        temp = os.path.join(os.path.dirname(__file__), 'templates/contacts.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
        
    def post(self):
        accept = self.request.get('accept')
        decline = self.request.get('decline')
        remove = self.request.get('remove')
        cancel = self.request.get('cancel')
        if accept:
            thisContact = return_current_contact(self)
            thatContact = db.get(accept)
            if  thatContact.key() in thisContact.incomingContacts and thisContact.key() in thatContact.outgoingContacts:
                thisContact.incomingContacts.remove(thatContact.key())
                thisContact.confirmedContacts.append(thatContact.key())
                thatContact.outgoingContacts.remove(thisContact.key())
                thatContact.confirmedContacts.append(thisContact.key())
                thisContact.put();
                thatContact.put();
        elif decline:
            thisContact = return_current_contact(self)
            thatContact = db.get(decline)
            if  thatContact.key() in thisContact.incomingContacts and thisContact.key() in thatContact.outgoingContacts:
                thisContact.incomingContacts.remove(thatContact.key())
                thatContact.outgoingContacts.remove(thisContact.key())
                thisContact.put();
                thatContact.put();
        elif remove:
            thisContact = return_current_contact(self)
            thatContact = db.get(remove)
            if  thatContact.key() in thisContact.confirmedContacts and thisContact.key() in thatContact.confirmedContacts:
                thisContact.confirmedContacts.remove(thatContact.key())
                thatContact.confirmedContacts.remove(thisContact.key())
                thisContact.put();
                thatContact.put();
        elif cancel:
            thisContact = return_current_contact(self)
            thatContact = db.get(cancel)
            if  thatContact.key() in thisContact.outgoingContacts and thisContact.key() in thatContact.incomingContacts:
                thisContact.outgoingContacts.remove(thatContact.key())
                thatContact.incomingContacts.remove(thisContact.key())
                thisContact.put();
                thatContact.put();
        self.redirect("/contacts")
        
class AddContactsPage(webapp2.RequestHandler):
    def get(self):
        template_values = { }
        
        template_values = dict(template_values.items() + base_dictionary(self).items())

        temp = os.path.join(os.path.dirname(__file__), 'templates/addcontacts.html')
        outstr = template.render(temp, template_values)
        self.response.out.write(outstr)
    def post(self):
        emails = self.request.get('emails')
        if emails:
            emaillist = emails.split();
            requestor = return_current_contact(self);
            for email in emaillist:
                invitee = return_contact_for_email(self, email)
                if requestor.key() != invitee.key():
                    if not invitee.key() in requestor.confirmedContacts:
                        if not invitee.key() in requestor.incomingContacts:
                            if not invitee.key() in requestor.outgoingContacts:
                                if not requestor.key() in invitee.confirmedContacts:
                                    if not requestor.key() in invitee.incomingContacts:
                                        if not requestor.key() in invitee.outgoingContacts:
                                            requestor.outgoingContacts.append(invitee.key())
                                            invitee.incomingContacts.append(requestor.key())
                                            requestor.put()
                                            invitee.put()
        self.redirect("/contacts")
            
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
                               ('/admin', AdminPage),
                               ('/events/manage', ManageEventsPage),
                               ('/events/add', AddEventPage),
                               ('/contacts', ContactsPage),
                               ('/contacts/add', AddContactsPage)]

app = webapp2.WSGIApplication(routes=routes,
                              config=config,
                              debug=True)
