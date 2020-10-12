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

# swagger config
app.config['SWAGGER'] = {
    'openapi': '3.0.3',
    'uiversion': 3,
    'specs_route': '/apidocs/'
}

swagger_template = {
   "info": {
      "title": "Graph Explorer REST API",
      "description": "A REST API for a graph of nodes and edges.",
      "version": "0"
    },
    "contact": {
      "name": "Andrew Mackie"
    },
    "components": {
        "schemas": {
            "node": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "required": False,
                        "title": "An optional and unique string to describe this node"
                    },
                    "_color": {
                        "type": "string",
                        "required": False,
                        "title": "An optional hex color for this node, including the # character (e.g. '#09A2d2')"
                    }
                }
            },
            "edge": {
                "type": "object",
                "properties": {
                    "sid": {
                        "type": "integer",
                        "required": True,
                        "description": "The id of the source node (the first node connected by this edge)"
                    },
                    "tid": {
                        "type": "integer",
                        "required": True,
                        "description": "The id of the target node (the second node connected by this edge)"
                    },
                    "name": {
                        "type": "string",
                        "default": None,
                        "required": False,
                        "description": "An optional and unique string to describe this edge"
                    },
                    "_color": {
                        "type": "string",
                        "default": None,
                        "required": False,
                        "description": "An optional hex color for this edge, including the # character (e.g. '#09A2d2')"
                    }
                }
            },
            "graph": {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            '$ref': '#/components/schemas/node'
                        }
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            '$ref': '#/components/schemas/edge'
                        }
                    }
                }
            },

        }
    }
}

swagger = Swagger(app, template=swagger_template)

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
    """Get the entire graph of nodes and edges
    ---
    description: Returns all nodes and edges in the database
    responses:
      200:
        description: An object containing a list of nodes and ed.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
    """
    if request.method == 'OPTIONS':
        # This is a CORS preflight request
        return {}, 200
    return get_graph(), 200


@app.route('/api/v0/node/<int:id>', methods=['GET'])
def node_get(id):
    """Get a node
    ---
    description: Returns a node based on id
    parameters:
      - name: id
        in: path
        description: The integer identifying the node
        required: true
        schema:
          type: integer
    responses:
      200:
        description: The data for this node
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/node'
      404:
        description: The node does not exist
        content:
          text/plain:
            schema:
              type: string

    """
    try:
        node = db.session.query(Node).filter_by(id=id).first()
        if node:
            return {'id': node.id, 'name': node.name, '_color': node.color}
        return f'Sorry, there is no node with id {id}', 404
    except Exception as e:
        return f'Sorry, there was an exception: {e}', 501


@app.route('/api/v0/node', methods=['POST'])
def node_post():
    """Create a new node
    ---
    description: Create a new node
    requestBody:
      description: Optional data describing the new node
      required: false
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/node'
    responses:
      201:
        description: The node has successfully been created.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'

      400:
        description: A node with the same name already exists.
        content:
          text/plain:
            schema:
              type: string
      501:
        description: Internal server error.
        content:
          text/plain:
            schema:
              type: string

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


@app.route('/api/v0/node/<int:id>', methods=['PUT'])
def node_put(id):
    """Update or create a node.
    ---
    description: Update or create a node with a specific id.
    parameters:
      - name: id
        in: path
        description: The integer identifying the node
        required: true
        schema:
          type: integer
    requestBody:
      description: Optional data describing the new node
      required: false
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/node'
    responses:
      200:
        description: The node has successfully been updated.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
      201:
        description: The node has successfully been created.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
      501:
        description: Internal server error.
        content:
          text/plain:
            schema:
              type: string
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


@app.route('/api/v0/node/<int:id>', methods=['DELETE'])
def node_delete(id):
    """Delete a node
    ---
    description: Returns a node based on id
    parameters:
      - name: id
        in: path
        description: The integer identifying the node
        required: true
        schema:
          type: integer
    responses:
      200:
        description: The node has been deleted.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
      404:
        description: The node does not exist
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


@app.route('/api/v0/edge/<int:id>', methods=['GET'])
def edge_get(id):
    """Get an edge
    ---
    description: Returns an edge based on id
    parameters:
      - name: id
        in: path
        description: The integer identifying the edge
        required: true
        schema:
          type: integer
    responses:
      200:
        description: The data for this edge
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/edge'
      404:
        description: The edge does not exist
        content:
          text/plain:
            schema:
              type: string
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


@app.route('/api/v0/edge', methods=['POST'])
def edge_post():
    """Create a new edge
    ---
    description: Create a new edge
    requestBody:
      description: Optional data describing the new edge
      required: false
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/edge'
    responses:
      201:
        description: The edge has successfully been created.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'

      400:
        description: An edge with the same name already exists.
        content:
          text/plain:
            schema:
              type: string
      501:
        description: Internal server error.
        content:
          text/plain:
            schema:
              type: string

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


@app.route('/api/v0/edge/<int:id>', methods=['PUT'])
def edge_put(id):
    """Update or create an edge.
    ---
    description: Update or create an edge with a specific id.
    parameters:
      - name: id
        in: path
        description: The integer identifying the edge
        required: true
        schema:
          type: integer
    requestBody:
      description: Optional data describing the new edge
      required: false
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/edge'
    responses:
      200:
        description: The edge has successfully been updated.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
      201:
        description: The edge has successfully been created.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
      501:
        description: Internal server error.
        content:
          text/plain:
            schema:
              type: string
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


@app.route('/api/v0/edge/<int:id>', methods=['DELETE'])
def edge_delete(id):
    """Delete an edge
    ---
    description: Returns an edge based on id
    parameters:
      - name: id
        in: path
        description: The integer identifying the edge
        required: true
        schema:
          type: integer
    responses:
      200:
        description: The edge has been deleted.
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/graph'
      404:
        description: The edge does not exist
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


@app.route('/api/v0/<noun>', methods=['OPTIONS'])
@app.route('/api/v0/<noun>/<int:id>', methods=['OPTIONS'])
def api_cors_preflight(noun, id):
    """For performance, return empty responses to CORS preflight requests (to avoid database calls)
    :return:
    """
    if noun in ['node', 'edge']:
        return {}, 200


if __name__ == '__main__':
    app.run()
