"""A RESTful CRUD API for a graph with endpoints for nodes and edges"""

from bleach import clean
from flasgger import Swagger
from flask import Flask, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
from sqlalchemy.schema import CheckConstraint

app = Flask(__name__)

# Use flasgger to automatically render and serve OpenAPI documentation (from comments in each route)
# Create an APISpec
template = {
    'title': 'Graph Explorer REST API',
    'description': 'A REST API for a graph of nodes and edges.',
    'version': '0',
    'contact': {
      'name': 'Andrew Mackie',
    },
    'headers': [
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
        ('Access-Control-Allow-Credentials', 'true'),
    ],
    'components': {
        'schemas': {
            'Node': {
                'type': 'object',
                'properties': {
                    'id': {
                        'type': 'integer',
                        'required': True,
                        'description': 'The unique identifier for this node'
                    },
                    'name': {
                        'type': 'string',
                        'default': None,
                        'required': False,
                        'unique': True,
                        'description': 'An optional and unique string to describe this node'
                    },
                    '_color': {
                        'type': 'string',
                        'default': None,
                        'required': False,
                        'description': "An optional hex color for this node, including the # character (e.g. '#09A2d2')"
                    },

                }
            },
            'Edge': {
                'type': 'object',
                'properties': {
                    'id': {
                        'type': 'integer',
                        'required': True,
                        'description': 'The unique identifier for this node'
                    },
                    'sid': {
                        'type': 'integer',
                        'required': True,
                        'description': 'The id of the source node (the first node connected by this edge)'
                    },
                    'tid': {
                        'type': 'integer',
                        'required': True,
                        'description': 'The id of the target node (the second node connected by this edge)'
                    },
                    'name': {
                        'type': 'string',
                        'default': None,
                        'required': False,
                        'unique': True,
                        'description': 'An optional and unique string to describe this edge'
                    },
                    '_color': {
                        'type': 'string',
                        'default': None,
                        'required': False,
                        'description': "An optional hex color for this edge, including the # character (e.g. '#09A2d2')"
                    },

                }
            }
        }
    }
}

# swagger config
app.config['SWAGGER'] = {
    'title': 'Graph Explorer API',
    'uiversion': 3,
    "specs_route": "/apidocs/"
}

swagger = Swagger(app, template= template)

CORS(app)  # Allow all CORS origins for all routes
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = 'False'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)


# Define the schema
class Node(db.Model):
    """A SQLAlchemy Class for storing nodes in Postgres."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=True, index=True)
    color = db.Column(db.String(7), unique=False, nullable=True, index=True)
    def __repr__(self):
        return f'<Node {self.id}'


class Edge(db.Model):
    """A SQLAlchemy Class for storing edges in Postgres.
    A CheckConstraint is applied to ensure that no edges are self-references (a node with an edge to itself)
    An edge is from a source node (sid) to a target node (tid)
    """
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(
        db.Integer,
        db.ForeignKey('node.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        index=True
    )
    tid = db.Column(
        db.Integer,
        db.ForeignKey('node.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(80), unique=True, nullable=True, index=True)
    color = db.Column(db.String(7), unique=False, nullable=True, index=True)
    __table_args__ = (CheckConstraint('sid != tid'),)  # <- Comma required as __table_args__ is a tuple
    def __repr__(self):
        return f'<Edge {self.sid} {self.tid}'


@app.route('/')
def welcome():
    return '<p>Welcome to Graph Explorer!</p><p>View the  <a href="/apidocs">API documentation</a>'


'''
The API has a wrapper which defines the Flask route and identifies the noun and method for the request.
The wrapper then allocates the request to the appropriate function (for the noun and method).
This architecture allows these unit-tested functions to be reused by other routes in the future.
'''
def get_graph():
    """Return the entire graph in the format required by vue-d3 network in the frontend."""
    return {
        'nodes': [{'id': r.id, 'name': r.name, '_color': r.color} for r in db.session.query(Node).all()],
        'edges': [
            {'id': r.id, 'sid': r.sid, 'tid': r.tid, 'name': r.name, '_color': r.color} for r in
            db.session.query(Edge).all()
        ]
    }


@app.route('/api/v0/graph')
def graph():
    """Returns the entire graph of nodes and edges
    ---
    definitions:
      Node:
          $ref: '#/components/schemas/Node'
      Edge:
          $ref: '#/components/schemas/Edge'
    responses:
      200:
        description: Returns the entire graph (all nodes and all edges in the database)
    """
    if request.method == 'OPTIONS':
        # This is a CORS preflight request
        return {}, 200
    return get_graph(), 200


def node_get(id):
    """Read a node
    :return: The node's data
    """
    try:
        node = db.session.query(Node).filter_by(id=id).first()
        if node:
            return {'id': node.id, 'name': node.name, '_color': node.color}
        return f'Sorry, there is no node with id {id}', 404
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


# These functions are separated from the API routes in order to make them reusable.
# (i.e. the Flask routes become an API wrapper for these functions)
def node_post():
    """Create a new node
    :return: The entire graph
    """
    # Clean the posted data to prevent XSS
    # Get the data in the request (cleaned to prevent XSS)
    try:
        name = clean(request.json.get('name') or '') or None
        color = clean(request.json.get('_color') or '') or None
        # Check whether there's an existing node with this name
        node_existing = db.session.query(Node).filter_by(name=name).first()
        if node_existing:
            return f'Sorry, a node with the name \'{name}\' already exists. Please change the name and try again.', 400
        node = Node(name=name, color=color)
        db.session.add(node)
        db.session.commit()
        return get_graph(), 201
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


def node_put(id):
    """Update or create a node.
    In this demo, there is no provision for updating the Postgres sequence id if records are created here.
    :return: The entire graph
    """
    # Get the data in the request (cleaned to prevent XSS)
    try:
        # Check whether the node exists
        node = db.session.query(Node).filter_by(id=id).first()
        if node:
            # Update only the parameters provided in the request data
            if 'name' in request.json:
                node.name = clean(request.json.get('name') or '') or None
            if '_color' in request.json:
                node.color = clean(request.json.get('_color') or '') or None
            db.session.commit()
            return get_graph(), 200
        else:
            # Create the node
            name = clean(request.json.get('name') or '') or None
            color = clean(request.json.get('_color') or '') or None
            node = Node(id=id, name=name, color=color)
            db.session.add(node)
            db.session.commit()
            return get_graph(), 201
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


def node_delete(id):
    """Delete a node
    :return: The entire graph
    """
    try:
        node = db.session.query(Node).filter_by(id=id).first()
        if node:
            try:
                db.session.delete(node)
                db.session.commit()
                return get_graph(), 200
            except Exception as e:
                return str(e), 501
        return f'There is no node with id={id}. Perhaps it has already been deleted?', 404
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


def edge_get(id):
    """Read a edge
    :return: The edge
    """
    try:
        edge = db.session.query(Edge).filter_by(id=id).first()
        if edge:
            return {
                'id': edge.id,
                'sid': edge.sid,
                'tid': edge.tid,
                'name': edge.name,
                '_color': edge.color
            }
        return f'Sorry, there is no edge with id {id}', 404
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


def edge_post():
    """Create a new edge
    :return: The entire graph
    """
    # Clean the posted data to prevent XSS
    # Get the data in the request (cleaned to prevent XSS)
    try:
        sid = request.json.get('sid')
        tid = request.json.get('tid')
        name = clean(request.json.get('name') or '') or None
        color = clean(request.json.get('_color') or '') or None
        db.session.add(Edge(sid=sid, tid=tid, name=name, color=color))
        db.session.commit()
        return get_graph(), 201
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


def edge_put(id):
    """Update or create a edge.
    In this demo, there is no provision for updating the Postgres sequence id if records are created here.
    :return: The entire graph
    """
    # Get the data in the request (cleaned to prevent XSS)
    try:
        # Check whether the edge exists
        edge = db.session.query(Edge).filter_by(id=id).first()
        if edge:
            # Update only the parameters provided in the request data
            if 'sid' in request.json and isinstance(request.json['sid'], int):
                edge.sid = request.json['sid']
            if 'tid' in request.json and isinstance(request.json['tid'], int):
                edge.tid = request.json['tid']
            if 'name' in request.json:
                edge.name = clean(request.json.get('name') or '') or None
            if '_color' in request.json:
                edge.color = clean(request.json.get('_color') or '') or None
            db.session.commit()
            return get_graph(), 200
        else:
            # Create the edge
            if isinstance(request.json.get('sid'), int) and isinstance(request.json.get('tid'), int):
                sid = request.json['sid']
                tid = request.json['tid']
            else:
                return 'Sorry, the sid and tid params must be integers.', 400
            name = clean(request.json.get('name') or '') or None
            color = clean(request.json.get('_color') or '') or None
            edge = Edge(id=id, sid=sid, tid=tid, name=name, color=color)
            db.session.add(edge)
            db.session.commit()
            return get_graph(), 201
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


def edge_delete(id):
    """Delete an edge
    :return: The entire graph
    """
    try:
        edge = db.session.query(Edge).filter_by(id=id).first()
        if edge:
            try:
                db.session.delete(edge)
                db.session.commit()
                return get_graph(), 200
            except Exception as e:
                return str(e), 501
        return f'There is no edge with id={id}. Perhaps it has already been deleted?', 404
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


# The routes (API wrappers) for the above functions

@app.route('/api/v0/<noun>', methods=['POST'])
def api_post(noun):
    """Define the Create function of the API
    :return:
    """
    if request.method == 'OPTIONS':
        # This is a CORS preflight request
        return {}, 200
    if noun == 'node':
        return node_post()
    if noun == 'edge':
       return edge_post()
    # The noun is unsupported
    return f'Sorry, the noun \'{noun}\' is not supported by this API.', 404


@app.route('/api/v0/<noun>/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def api_get_put_delete(noun, id):
    """Define the Read, Update and Delete functions of the API
    :return:
    """
    if request.method == 'OPTIONS':
        # This is a CORS preflight request
        return {}, 200
    if noun == 'node':
        if request.method == 'GET':
            return node_get(id)
        if request.method == 'PUT':
            return node_put(id)
        if request.method == 'DELETE':
            return node_delete(id)
    if noun == 'edge':
        if request.method == 'GET':
           return edge_get(id)
        if request.method == 'PUT':
           return edge_put(id)
        if request.method == 'DELETE':
           return edge_delete(id)
    # The noun is unsupported
    return f'Sorry, the noun \'{noun}\' is not supported by this API.', 404


if __name__ == '__main__':
    app.run()
