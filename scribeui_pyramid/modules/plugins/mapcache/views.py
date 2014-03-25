# Job status
#    0 - Finished 
#    1 - In progress
#    2 - Stopped (error)

#from flask import Flask, Blueprint, render_template, url_for, current_app, request, g, jsonify
import logging
import transaction

from pyramid.httpexceptions import (
    HTTPFound,
    HTTPNotFound
)
from pyramid.view import view_config

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import exc

log = logging.getLogger(__name__)

#import simplejson, pprint, sys, os
import pprint, sys, os

from .processManager import processManager

from .. import DBSession
from .. import Map
from .. import Workspace

from .models import Job

#sys.path.append("../../") # Gives access to init.py functions

#plugin = Blueprint('mapcache', __name__, static_folder='static', template_folder='templates')

#def getJsFiles():
#    createTable()
#    return url_for('mapcache.static',filename='js/mapcache.js')

#def getCssFiles():
#    return url_for('mapcache.static',filename='css/mapcache.css')

class APIMapcache(object):

    def __init__(self, request):
        self.request = request
        self.matchdict = request.matchdict

        
    @view_config(
        route_name='mapcache.startjob',
        permission='view',
        renderer='json',
        request_method='POST'
    )
    def startJob(self):
        response = {
            'status': 0,
            'errors': [],
            'job': {}
            }

        extent = None
        dbconfig = None
        
        try:
            mapID = self.request.POST.get('map')
            if mapID == '':
                response['errors'].append('An map ID is required.')
        except KeyError as e:
            response['errors'].append('A map ID is required.')

        try:
            title = self.request.POST.get('title')
            if title == '':
                response['errors'].append('A job title is required.')
        except KeyError as e:
            response['errors'].append('A job title is required.')

        try:
            zoomLevels = self.request.POST.get('zoomlevels')
            if zoomLevels == '':
                response['errors'].append('Zoom levels are required.')
        except KeyError as e:
            response['errors'].append('Zoom levels are required.')

        try:
            metatile = self.request.POST.get('metatile')
            if metatile == '':
                response['errors'].append('Metatiles size is required.')
        except KeyError as e:
            response['errors'].append('Metatiles size is required.')

        try:
            extent_type = self.request.POST.get('type')
            if extent_type == '':
                response['errors'].append('Extent type is required.')
        except KeyError as e:
            response['errors'].append('Extent type is required.')

        if len(response['errors']) == 0:
            if extent_type == 'string':
                try:
                    extent = self.request.POST.get('extent')
                    if extent == '':
                        response['errors'].append('An extent is required.')
                except KeyError as e:
                    response['errors'].append('An extent is required.')
            else:
                try:
                    dbhost = self.request.POST.get('dbhost')
                    if dbhost == '':
                        response['errors'].append('Host name is required.')
                except KeyError as e:
                    response['errors'].append('Host name is required.')

                try:
                    dbport = self.request.POST.get('dbport')
                    if dbport == '':
                        response['errors'].append('Database port is required.')
                except KeyError as e:
                    response['errors'].append('Database port is required.')

                try:
                    dbname = self.request.POST.get('dbname')
                    if dbname == '':
                        response['errors'].append('Database name is required.')
                except KeyError as e:
                    response['errors'].append('Database name is required.')

                try:
                    dbuser = self.request.POST.get('dbuser')
                    if dbuser == '':
                        response['errors'].append('Database user is required.')
                except KeyError as e:
                    response['errors'].append('Database user is required.')

                try:
                    dbpassword = self.request.POST.get('dbpassword')
                    if dbpassword == '':
                        dbpassword = None
                except KeyError as e:
                    dbpassword = None

                try:
                    dbquery = self.request.POST.get('dbquery')
                    if dbquery == '':
                        response['errors'].append('A query is required.')
                except KeyError as e:
                    response['errors'].append('A query is required.')

                if len(response['errors']) == 0:
                    dbconfig = {
                        'type': extent_type,
                        'host': dbhost,
                        'port': dbport,
                        'name': dbname,
                        'user': dbuser,
                        'password': dbpassword,
                        'query': dbquery    
                    }
                

            if len(response['errors']) == 0:               
                try:
                    map = Map.by_id(mapID)
                except NoResultFound, e:
                    response['errors'].append('This map is unavailable or does not exist.')

                if len(response['errors']) == 0:
                    workspace = Workspace.by_id(map.workspace_id)
                    if(workspace.name == self.request.userid):
                        workspaces_directory = self.request.registry.settings.get('workspaces.directory', '') + '/'
                        map_directory = workspaces_directory + self.request.userid + '/' + map.name + '/'
                        mapfile = map_directory + 'map/' + map.name + '.map' 

                        kwargs = {
                            'title': title,
                            'status': 1,
                            'map_id': mapID
                        }

                        job = Job(**kwargs)

                        try:
                            DBSession.add(job)
                            #used to get the job id
                            DBSession.flush()
                        except exc.SQLAlchemyError as e:
                            response['errors'].append(e)

                           
                        if len(response['errors']) == 0:

                            pManager = processManager()
                            pManager.addProcess(job, map_directory, mapfile, zoomLevels, metatile, extent=extent, dbconfig=dbconfig)

                            kwargs['id'] = job.id
                            response['job'] = kwargs
                            response['status'] = 1
                    else:
                        response['errors'].append('Access denied.')
             
        return response


    @view_config(
        route_name='mapcache.getjobs',
        permission='view',
        renderer='json',
        request_method='GET'
    )
    def getJobs(self):
        response = {
            'status': 0,
            'errors': [],
            'jobs': []
            }

        try:
            wsID = self.request.GET.get('ws')
        except KeyError as e:
            response['errors'].append('A workspace id is required.')

        if len(response['errors']) == 0:
            workspace = Workspace.by_name(wsID)
            if(workspace.name == self.request.userid):
                query = DBSession.query(
                    Job.id,
                    Job.title, 
                    Job.status, 
                    Job.map_id,
                    Map.workspace_id,
                    Map.id,
                    Map.name) \
                    .filter(Map.workspace_id == workspace.id, Job.map_id == Map.id)

                jobs = query.all()            

                for job in jobs:
                    response['jobs'].append({
                        'id': job[0],
                        'title': job[1],
                        'status': job[2],
                        'map_name': job[6]
                        })

                response['status'] = 1
            else:
                response['errors'].append('Access denied.')

        return response

    @view_config(
        route_name='mapcache.stopjob',
        permission='view',
        renderer='json',
        request_method='GET'
    )
    def stopJob(self):
        response = {
            'status': 0,
            'errors': [],
            'log': ''
            }
        #TODO : prevent clearing job from another workspace than the current one
        try:
            id = self.request.GET.get('job')
        except KeyError as e:
            response['errors'].append('A job id is required.')

        if len(response['errors']) == 0:
            try:
                job = Job.by_id(id)
            except NoResultFound, e:
                response['errors'].append('Job not found. Was it cleared already?')

            if len(response['errors']) == 0:
                if job.status == 1:
                    pManager = processManager()
                    pManager.stopProcess(job.id, False)
                    try:
                        job.status = 2
                        transaction.commit()
                    except exc.SQLAlchemyError as e:
                        response['errors'].append("An error occured while updating job status.")
                else:
                    response['errors'].append("Job was already finished or stopped.")

                if len(response['errors']) == 0:
                    response['status'] = 1
                    response['log'] = 'Job ' + str(id) + ' has been stopped.'

        return response


    @view_config(
        route_name='mapcache.clearjob',
        permission='view',
        renderer='json',
        request_method='GET'
    )
    def clearJob(self):
        response = {
            'status': 0,
            'errors': [],
            'log': ''
            }
        #TODO : prevent clearing job from another workspace than the current one
        try:
            id = self.request.GET.get('job')
        except KeyError as e:
            response['errors'].append('A job id is required.')

        if len(response['errors']) == 0:
            try:
                job = Job.by_id(id)
            except NoResultFound, e:
                response['errors'].append('Job not found. Was it cleared already?')

            if len(response['errors']) == 0:
                if job.status == 1: #Cancel clear if job is still in progress 
                    response['errors'].append('Job is in progress, please stop before clearing')
                else:    
                    try:
                        DBSession.delete(job)
                    except exc.SQLAlchemyError as e:
                        response['errors'].append("An error occured whileclearing the job.")
                
                if len(response['errors']) == 0:
                    response['status'] = 1
                    response['log'] = 'Job ' + str(id) + ' has been cleared.'
        
        return response  