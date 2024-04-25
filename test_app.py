import pytest
from flask import url_for
from app import app, db, OrdersRow, ProductsRow
from peewee import SqliteDatabase
from app import initialize_products

test_db = SqliteDatabase(':memory:')

#pytest test_app.py

# Client
@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = 'localhost:5000'
    with app.app_context():
        with app.test_client() as client:
            yield client

# Base de donnée
@pytest.fixture
def database():
    with test_db.bind_ctx([OrdersRow, ProductsRow]):
        test_db.create_tables([OrdersRow, ProductsRow])
        # Initialize the products
        initialize_products()
        yield test_db
        test_db.drop_tables([OrdersRow, ProductsRow])

# Tests 

def test_showProducts(client, database):
    response = client.get(url_for('showProducts'))
    assert response.status_code == 200

def test_createOrder(client, database):
    response = client.post(url_for('createOrder'), json={
        "product": {
            "id": 1,
            "quantity": 1
        }
    })
    assert response.status_code == 302

def test_order_route(client, database):
    response = client.get(url_for('order_route', identifier=1))
    assert response.status_code == 404

def test_order_route_update(client, database):
    client.post(url_for('createOrder'), json={
        "product": {
            "id": 1,
            "quantity": 1
        }
    })
    response2 = client.put(url_for('order_route', identifier=1), json={
        "order" : {
        "email" : "jgnault@uqac.ca",
        "shipping_information" : {
        "country" : "Canada",
        "address" : "201, rue Président-Kennedy",
        "postal_code" : "G7X 3Y7",
        "city" : "Chicoutimi",
        "province" : "QC"
        }
        }
        })
    assert response2.status_code == 200

def test_order_route_update_missing_email(client, database):
    client.post(url_for('createOrder'), json={
        "product": {
            "id": 1,
            "quantity": 1
        }
    })
    response = client.put(url_for('order_route', identifier=1), json={
        "order" : {
        "shipping_information" : {
        "country" : "Canada",
        "address" : "201, rue Président-Kennedy",
        "postal_code" : "G7X 3Y7",
        "city" : "Chicoutimi",
        "province" : "QC"
        }
        }
        })
    assert response.status_code == 400

def test_order_route_payment_valid(client, database):
    client.post(url_for('createOrder'), json={
        "product": {
            "id": 1,
            "quantity": 1
        }
    })
    client.put(url_for('order_route', identifier=1), json={
        "order" : {
        "email" : "jgnault@uqac.ca",
        "shipping_information" : {
        "country" : "Canada",
        "address" : "201, rue Président-Kennedy",
        "postal_code" : "G7X 3Y7",
        "city" : "Chicoutimi",
        "province" : "QC"
        }
        }})
    response = client.put(url_for('order_route', identifier=1), json={
        "credit_card" : {
        "name" : "John Doe",
        "number" : "4242 4242 4242 4242",
        "expiration_year" : 2025,
        "cvv" : "123",
        "expiration_month" : 9
        }
        })
    assert response.status_code == 200


def test_order_route_payment_invalid(client, database):
    client.post(url_for('createOrder'), json={
        "product": {
            "id": 1,
            "quantity": 1
        }
    })
    client.put(url_for('order_route', identifier=1), json={
        "order" : {
        "email" : "jgnault@uqac.ca",
        "shipping_information" : {
        "country" : "Canada",
        "address" : "201, rue Président-Kennedy",
        "postal_code" : "G7X 3Y7",
        "city" : "Chicoutimi",
        "province" : "QC"
        }
        }})
    response = client.put(url_for('order_route', identifier=1), json={
        "credit_card" : {
        "name" : "John Doe",
        "number" : "4000 0000 0000 0002",
        "expiration_year" : 2025,
        "cvv" : "123",
        "expiration_month" : 9
        }
        })
    assert response.status_code == 422