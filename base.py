#!/usr/bin/python
import cherrypy
import sqlite3
import os
import re
import time

from mako.template import Template
from mako.lookup import TemplateLookup


SQLITE_DATABASE = "database.sqlite3"

# Our CherryPy application
tmplLookup = TemplateLookup(directories=['templates'], module_directory='tmp/mako')
class Root(object):
	
	def __init__(self):
		# self.api = API()
		pass

	@cherrypy.expose
	def index(self):
		tmpl = tmplLookup.get_template("index.mako.html")

		return tmpl.render()

	# @cherrypy.expose
	# def default(self, key=None, **kwargs):
	# 	raise cherrypy.HTTPRedirect("/") 


cherrypy.engine.subscribe('start', dbHandler.setup_database)
# cherrypy.engine.subscribe('stop', cleanup_database)

config = {
	"/favicon.ico": {
		"tools.staticfile.on" : True
		"tools.staticfile.filename" : os.path.join(os.path.dirname(os.path.realpath(__file__)), "static", "favicon.ico")
	},
	"/static": {
		"tools.staticdir.on" : True
		"tools.staticdir.dir" : os.path.join(os.path.dirname(os.path.realpath(__file__)), "static")
	}
}

wsgiapp = cherrypy.tree.mount(Root(), config=config)

if __name__ != "__main__":
	cherrypy.config.update({'engine.autoreload.on': False})
	cherrypy.server.unsubscribe()
	cherrypy.engine.start()
else:
	cherrypy.config.update({ 'server.socket_port': 9095, 'server.socket_host': "0.0.0.0"})
	cherrypy.quickstart(wsgiapp)