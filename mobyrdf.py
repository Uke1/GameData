'''
Created on 17 Sep 2019

@author: alexdma@apache.org

'''
import time

from SPARQLWrapper import SPARQLExceptions, SPARQLWrapper, JSON
from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS
from rdflib.namespace import FOAF, DCTERMS, SKOS
import requests
from requests.auth import HTTPBasicAuth

from config import config as cfg
from rdf_factories import Gaming, VGO
import rdf_factories as maker

API_KEY = cfg['moby']['api_key']
ENDPOINT = cfg['moby']['endpoint']
API_STEP = 100
DUL = Namespace('http://www.ontologydesignpatterns.org/ont/dul/DUL.owl#')
LDMoby = Namespace('http://data.datascienceinstitute.ie/mobygames/')

genre_mappings = {
     1 : { "property" : VGO.has_game_genre, "class" : VGO.Genre, "shorthand" : "genre" },
     2 : { "property" : Gaming.viewable_from_perspective, "class" : Gaming.ViewingPerspective, "shorthand" : "view" },
     3 : { "property" : Gaming.has_sport, "class" : Gaming.Sport, "shorthand" : "sport" },
     4 : { "property" : Gaming.has_gameplay_type, "class" : Gaming.Gameplay, "shorthand" : "gameplay" },
     5 : { "property" : Gaming.has_educational_genre, "class" : VGO.Genre, "shorthand" : "genre_edu" },
     6 : { "property" : Gaming.has_gameplay_feature, "class" : Gaming.GameplayFeature, "shorthand" : "gameplay_feature" },
     7 : { "property" : Gaming.has_interface, "class" : Gaming.InterfaceType, "shorthand" : "interface" },
     8 : { "property" : Gaming.is_about, "class" : SKOS.Concept, "shorthand" : "theme" },
     9 : { "property" : Gaming.has_gameplay_pacing, "class" : Gaming.Pacing, "shorthand" : "pacing" },
    10 : { "property" : DUL.hasSetting, "class" : DUL.Setting, "shorthand" : "setting" },
    11 : { "property" : Gaming.has_drivable_vehicle_type, "class" : Gaming.IngameVehicle, "shorthand" : "ingame_vehicle" },
    12 : { "property" : Gaming.presented_visually, "class" : Gaming.VisualPresentation, "shorthand" : "visual" },
    13 : { "property" : Gaming.has_artistic_style, "class" : Gaming.ArtStyle, "shorthand" : "art_style" },
    14 : { "property" : Gaming.is_addon_type, "class" : Gaming.AddonType, "shorthand" : "addon_type" },
    15 : { "property" : Gaming.is_edition, "class" : Gaming.EditionType, "shorthand" : "edition" }
}


def write(nt):
    sparql = SPARQLWrapper(cfg['storage']['sparql_update'])
    query = f"""
INSERT DATA {{ {nt} }}
"""
    sparql.setQuery(query)
    sparql.setCredentials(cfg['storage']['auth']['user'], cfg['storage']['auth']['password'])
    sparql.method = 'POST'
    sparql.query()


def RateLimited(maxPerSecond):
    minInterval = 1.0 / float(maxPerSecond)

    def decorate(func):
        lastTimeCalled = [0.0]

        def rateLimitedFunction(*args, **kargs):
            elapsed = time.perf_counter() - lastTimeCalled[0]
            leftToWait = minInterval - elapsed
            if leftToWait > 0:
                time.sleep(leftToWait)
            ret = func(*args, **kargs)
            lastTimeCalled[0] = time.perf_counter()
            return ret

        return rateLimitedFunction

    return decorate


@RateLimited(0.1)  # One in ten seconds
def callMoby(resource, auth, filename=None):
    print('calling ' + resource)
    response = requests.get('/'.join((ENDPOINT, resource)), auth=auth)
    return response.json()


def games(details=False):
    lastNoRes = 1
    page = 0
    auth = HTTPBasicAuth(API_KEY, '')
    key = 'games'
    path = key
    while lastNoRes > 0 and lastNoRes <= API_STEP:
        json = callMoby(path + '?offset=' + str(API_STEP * page) + '&format=' + ('normal' if details else 'id'), auth)
        page += 1
        if key not in json:
            print('No key "' + key + '" in JSON! Printout follows')
            print(json)
        lastNoRes = len(json[key])
        print('page {} : {} {}'.format(page, lastNoRes, key))
        graph = Graph()
        if details:
            for g in json[key] :
                guri = LDMoby + 'game/' + str(g["game_id"])
                game = maker.game(graph, guri, g['title'])      
                if 'description' in g :
                    graph.add((game, DCTERMS.description, Literal(g['description'], datatype=RDF.HTML)))
        else :
            for gid in json[key] :
                guri = LDMoby + 'game/' + str(gid)
                game = maker.game(graph, guri, g['title'])  
        write (graph.serialize(format='ntriples').decode('UTF-8'))


def genres():
    """
    Genres in MobyGames encode more than just genres
    """
    lastNoRes = 1
    page = 0
    auth = HTTPBasicAuth(API_KEY, '')
    key = 'genres'
    while lastNoRes > 0 and lastNoRes <= API_STEP:
        json = callMoby(key + '?offset=' + str(API_STEP * page), auth)
        page += 1
        if key not in json:
            print('No key "' + key + '" in JSON! Printout follows')
            print(json)
        lastNoRes = len(json[key])
        print('page {} : {} {}'.format(page, lastNoRes, key))
        graph = Graph()
        for p in json[key] :
            cat_id = p["genre_category_id"]
            if cat_id not in genre_mappings :
                raise Exception("I didn't know genre {} : {}".format(cat_id, p["genre_category"]))
            genre = URIRef(LDMoby + genre_mappings[cat_id]['shorthand'] + '/' + str(p['genre_id']))
            graph.add((genre_mappings[cat_id]['class'], RDFS.label, Literal(p["genre_category"], lang='en')))
            graph.add((genre, RDF.type, genre_mappings[cat_id]['class']))
            graph.add((genre, RDFS.label, Literal(p["genre_name"], lang='en')))
            graph.add((genre, DCTERMS.description, Literal(p["genre_description"], lang='en')))
            # The genre category pretty much determines the property
        write (graph.serialize(format='ntriples').decode('UTF-8'))


def groups():
    """
    Genres in MobyGames encode more than just genres
    """
    lastNoRes = 1
    page = 0
    auth = HTTPBasicAuth(API_KEY, '')
    key = 'groups'
    while lastNoRes > 0 and lastNoRes <= API_STEP:
        json = callMoby(key + '?offset=' + str(API_STEP * page), auth)
        page += 1
        if key not in json:
            print('No key "' + key + '" in JSON! Printout follows')
            print(json)
        lastNoRes = len(json[key])
        print('page {} : {} {}'.format(page, lastNoRes, key))
        graph = Graph()
        for p in json[key] :
            guri = LDMoby + 'game_group/' + str(p['group_id'])
            group = maker.group(graph, guri, p["group_name"], p["group_description"])
        write (graph.serialize(format='ntriples').decode('UTF-8'))
        # Now games in the group
        for p in json[key] :
            lastNoResGiG = 1
            pageGiG = 0
            while lastNoResGiG > 0 and lastNoResGiG <= API_STEP:
                graph = Graph()
                guri = LDMoby + 'game_group/' + str(p['group_id'])
                group = maker.group(graph, guri, p["group_name"], p["group_description"])
                groupJson = callMoby('games?group=' + str(p['group_id']) + "&format=id" + '&offset=' + str(API_STEP * pageGiG), auth)
                pageGiG += 1
                lastNoResGiG = len(groupJson['games'])
                if 'games' in groupJson:
                    print('Group {} has {} games left to process.'.format(p['group_id'], len(groupJson['games'])))
                    for game_id in groupJson['games']:
                        game = URIRef(LDMoby + 'game/' + str(game_id))
                        maker.game2group(graph, game, group)
                write (graph.serialize(format='ntriples').decode('UTF-8'))
        

def platforms():
    lastNoRes = 1
    page = 0
    auth = HTTPBasicAuth(API_KEY, '')
    key = 'platforms'
    tPlatform = URIRef(LDMoby + 'term/' + 'GamingPlatform')
    while lastNoRes > 0 and lastNoRes <= API_STEP:
        json = callMoby(key + '?offset=' + str(API_STEP * page), auth)
        page += 1
        if key not in json:
            print('No key "' + key + '" in JSON! Printout follows')
            print(json)
        lastNoRes = len(json[key])
        print('page {} : {} {}'.format(page, lastNoRes, key))
        graph = Graph()
        for p in json[key] :
            platform = URIRef(LDMoby + 'platform/' + str(p['platform_id']))
            graph.add((platform, RDF.type, tPlatform))
            graph.add((platform, RDFS.label, Literal(p['platform_name'], lang='en')))
            graph.add((platform, FOAF.name, Literal(p['platform_name'])))
        write (graph.serialize(format='ntriples').decode('UTF-8'))

            
platforms()
genres()
# groups()
games(True)
groups()
