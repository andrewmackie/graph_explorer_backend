"""Testing

Postgres
A Heroku pipeline is used to do CI on a staging app.
app.json tells Heroku to create a hobby-dev plan Postgres database for this.

Test Anything Protocol
Heroku CI will call "pytest --tap-stream" (from app.json) and pytest-tap (in requirements.txt) will automatically
format pytest results into Test Anything Protocol so that Heroku CI can interpret them.

"""

from app import app, db, Edge, Node
from faker import Faker
import pytest

# New node/edge data
sid = 3
tid = 6
name = 'foo'
color = '#000000'


@pytest.fixture
def client():
    """Load data for tests and return a Flask test_client"""
    app.debug = True
    db.create_all()
    db.session.execute('DELETE FROM node;')  # Edge deletes will cascade
    fake = Faker()
    for n in range(1, 11):
        db.session.add(Node(id=n, name=f'Node{n}', color=fake.hex_color()))
    db.session.commit()
    db.session.execute('ALTER SEQUENCE node_id_seq RESTART WITH 11;')
    db.session.execute('ALTER SEQUENCE edge_id_seq RESTART WITH 1;')
    for e in range(1, 10):
        db.session.add(Edge(sid=e, tid=e+1, name=f'Edge-{e}-{e+1}', color=fake.hex_color()))
    db.session.commit()
    return app.test_client()


def return_item_with_id(list_of_dictionaries, id):
    """Returns a dictionary with nominated id (from a list of dictionaries)"""
    for dictionary in list_of_dictionaries:
        if dictionary.get('id') == id:
            return dictionary
    return None


def test_graph_get(client):
    response = client.get('/api/v0/graph')
    assert response.status_code == 200
    assert len(response.json['nodes']) == 10
    assert len(response.json['edges']) == 9


def test_node_get(client):
    response = client.get('/api/v0/node/1')
    assert response.status_code == 200
    assert response.json['id'] == 1
    assert response.json['name'] == 'Node1'
    assert response.json['_color']


def test_node_post(client):
    response = client.post('/api/v0/node', json={'name': name, '_color': color})
    assert response.status_code == 201
    assert len(response.json['nodes']) == 11
    assert response.json['nodes'][10]['name'] == name
    assert response.json['nodes'][10]['_color'] == color


def test_node_put(client):
    response = client.put('/api/v0/node/1', json={'name': name, '_color': color})
    updated_node = return_item_with_id(response.json['nodes'], 1)
    assert response.status_code == 200
    assert updated_node['name'] == name
    assert updated_node['_color'] == color


def test_node_put_partial_1(client):
    existing_node_data = client.get('/api/v0/node/1').json
    response = client.put('/api/v0/node/1', json={'name': name})
    updated_node = return_item_with_id(response.json['nodes'], 1)
    assert response.status_code == 200
    assert updated_node['name'] == name
    assert updated_node['_color'] == existing_node_data['_color']


def test_node_put_partial_2(client):
    existing_node_data = client.get('/api/v0/node/1').json
    response = client.put('/api/v0/node/1', json={'_color': color})
    updated_node = return_item_with_id(response.json['nodes'], 1)
    assert response.status_code == 200
    assert updated_node['name'] == existing_node_data['name']
    assert updated_node['_color'] == color


def test_node_delete(client):
    response = client.delete('/api/v0/node/1')
    assert response.status_code == 200
    assert len(response.json['nodes']) == 9
    assert return_item_with_id(response.json['edges'], 1) == None


def test_edge_get(client):
    response = client.get('/api/v0/edge/1')
    assert response.status_code == 200
    assert response.json['id'] == 1
    assert response.json['name'] == 'Edge-1-2'
    assert response.json['sid'] == 1
    assert response.json['tid'] == 2
    assert response.json['_color']


def test_edge_post(client):
    response = client.post('/api/v0/edge', json={'sid': sid, 'tid': tid, 'name': name, '_color': color})
    new_edge = return_item_with_id(response.json['edges'], 10)
    assert response.status_code == 201
    assert len(response.json['edges']) == 10
    assert new_edge['sid'] == sid
    assert new_edge['tid'] == tid
    assert new_edge['name'] == name
    assert new_edge['_color'] == color


def test_edge_put(client):
    response = client.put('/api/v0/edge/1', json={'sid': sid, 'tid': tid, 'name': name, '_color': color})
    updated_edge = return_item_with_id(response.json['edges'], 1)
    assert response.status_code == 200
    assert updated_edge['sid'] == sid
    assert updated_edge['tid'] == tid
    assert updated_edge['name'] == name
    assert updated_edge['_color'] == color


def test_edge_put_partial_1(client):
    existing_edge_data = client.get('/api/v0/edge/1').json
    response = client.put('/api/v0/edge/1', json={'sid': sid, 'name': name})
    updated_edge = return_item_with_id(response.json['edges'], 1)
    assert response.status_code == 200
    assert updated_edge['sid'] == sid
    assert updated_edge['tid'] == existing_edge_data['tid']
    assert updated_edge['name'] == name
    assert updated_edge['_color'] == existing_edge_data['_color']


def test_edge_put_partial_2(client):
    existing_node_data = client.get('/api/v0/edge/1').json
    response = client.put('/api/v0/edge/1', json={'tid': tid, '_color': color})
    updated_edge = return_item_with_id(response.json['edges'], 1)
    assert response.status_code == 200
    assert updated_edge['sid'] == existing_node_data['sid']
    assert updated_edge['tid'] == tid
    assert updated_edge['name'] == existing_node_data['name']
    assert updated_edge['_color'] == color


def test_edge_delete(client):
    response = client.delete('/api/v0/edge/1')
    assert response.status_code == 200
    assert len(response.json['edges']) == 8
    assert return_item_with_id(response.json['edges'], 1) == None


def test_swag(client):
    """
    This test is runs automatically in Travis CI

    :param client: Flask app test client
    :param specs_data: {'url': {swag_specs}} for every spec in app
    """
    specs_data = client.get('/apispec_1.json').json
    print(specs_data)
    #for url, spec in specs_data.items():
    assert 'node' in specs_data['components']['schemas']
    assert 'edge' in specs_data['components']['schemas']
    assert 'graph' in specs_data['components']['schemas']
