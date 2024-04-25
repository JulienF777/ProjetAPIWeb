import os
from flask import Flask, request, jsonify, current_app, render_template
import requests
import json
import peewee
from peewee import PostgresqlDatabase, Model, CharField, IntegerField, FloatField, BooleanField, TextField, AutoField
from flask.cli import with_appcontext
import click
from playhouse.shortcuts import model_to_dict
import psycopg2
import codecs
from flask_caching import Cache
import redis
from redis import Redis
from rq import Queue, Worker, Connection

#Dockers
import pg8000

app = Flask(__name__)

# Connexion à Redis
redis = Redis.from_url("redis://cache:6379")
# Connexion à la file d'attente Redis
queue = Queue(connection=redis)
# nom de la file d'attente
listen = ['default']




# Connexion a la base de données PostgreSQL
#db = PostgresqlDatabase('db', user='postgres', password='root', host='database', port='5432')
db = PostgresqlDatabase(
    os.environ.get('POSTGRES_DB'),
    user=os.environ.get('POSTGRES_USER'),
    password=os.environ.get('POSTGRES_PASSWORD'),
    host=os.environ.get('POSTGRES_HOST'),
    port=int(os.environ.get('POSTGRES_PORT', 5432))  # Default port 5432 if not specified
)

# Set the FLASK_APP environment variable
os.environ["FLASK_APP"] = "inf349"

# rappel des fonctions pour lancer le serveur et initialiser la base de données

#python -m flask --app app init-db
#python -m flask --app app run
#FLASK_DEBUG=True FLASK_APP=inf349 flask init-db
#FLASK_DEBUG=True FLASK_APP=inf349 flask run


class OrdersRow(peewee.Model):
    orderid = peewee.AutoField(primary_key=True)
    total_price = peewee.FloatField(default=0.0)
    email = peewee.TextField(null=True)
    
    shipping_information = peewee.TextField(null=True)
    country = peewee.TextField(null=True)
    address = peewee.TextField(null=True)
    postal_code = peewee.TextField(null=True)
    city = peewee.TextField(null=True)
    province = peewee.TextField(null=True)

    paid = peewee.BooleanField(default=False)
    transaction = peewee.TextField(null=True)

    product = peewee.TextField(null=True)
    product_id = peewee.IntegerField(null=True) 
    quantity = peewee.IntegerField(null=True)
    shipping_price = peewee.FloatField(default=0.0, null=True)

    credit_card = peewee.TextField(null=True)
    name = peewee.TextField(null=True)
    number = peewee.TextField(null=True)
    expiration_year = peewee.IntegerField(null=True)
    cvv = peewee.TextField(null=True)
    expiration_month = peewee.IntegerField(null=True)

    debug = peewee.TextField(null=True)
    
    class Meta:
        database = db


class ProductsRow(peewee.Model):

    description = peewee.TextField(null=True)
    height = peewee.IntegerField(null=True)
    id = peewee.IntegerField(primary_key=True)
    image = peewee.TextField(null=True)
    in_stock = peewee.BooleanField(null=True)
    name = peewee.CharField(null=True)
    price = peewee.FloatField(null=True)
    type = peewee.TextField(null=True)
    weight = peewee.IntegerField(null=True)
    
    class Meta:
        database = db

# modèle pour la création de commande à pluisieurs produits.
class OrderProductsRow(peewee.Model):
    order = peewee.ForeignKeyField(OrdersRow, backref='order_products')
    product = peewee.ForeignKeyField(ProductsRow)
    quantity = peewee.IntegerField()

    class Meta:
        database = db

def clean_description(description):
    # nettoyer les caractères nuls dans la description
    return description.replace('\x00', '')

def initialize_products():
    # Récupération des produits à partir de l'API
    products = requests.get("http://dimprojetu.uqac.ca/~jgnault/shops/products/").json()

    for product in products['products']:
        try:
            product['description'] = clean_description(product['description'])
            ProductsRow.insert(**product).execute()
        except peewee.IntegrityError:
            print("erreur d'intégrité")
            # Gérer les erreurs d'intégrité si nécessaire
            pass



@app.route("/", methods=["GET"])
def showProducts():
    if request.method == "GET":
        # Récupération des produits depuis la base de données
        products_data = [model_to_dict(product) for product in ProductsRow.select()]
        return render_template("index.html", products=products_data)

        #response = {"products": products_data}
        #return jsonify(response)
    else:
        return "Fichier JSON à distance non récupéré.", 501


@app.route("/order", methods=["POST"])
def createOrder():
    if request.method == "POST":
        try:
            products = request.json.get("products", [])
            if not products:
                error_message = {
                    "errors": {
                        "product": {
                            "code": "empty-cart",
                            "name": "Le panier est vide. Ajoutez des produits avant de créer une commande."
                        }
                    }
                }
                return jsonify(error_message), 400

            if all("id" in product and "quantity" in product for product in products):
                order = OrdersRow.create(total_price=0.0)
                total_price = 0.0

                for product_data in products:
                    product_id = product_data["id"]
                    product_quantity = product_data["quantity"]
                    product = ProductsRow.get_or_none(ProductsRow.id == product_id)

                    if product and product.in_stock and product_quantity > 0:
                        # Calculate total price
                        total_price += (product.price * product_quantity)
                        # Create entry in OrderProductsRow to associate product with the order
                        OrderProductsRow.create(order=order, product=product, quantity=product_quantity)

                        # Update total price of the order
                        order.total_price = total_price
                        order.save()
                        
                    else:
                        error_message = {
                            "errors": {
                                "product": {
                                    "code": "out-of-inventory",
                                    "name": "Le produit demandé n'est pas en inventaire ou la quantité est invalide.",
                                }
                            }
                        }
                        return jsonify(error_message), 422
                return "Location: /order/" + str(order.orderid), 302
            else:
                error_message = {
                    "errors": {
                        "product": {
                            "code": "missing-fields",
                            "name": "La création d'une commande nécessite un produit avec un id et une quantité."
                        }
                    }
                }
                return jsonify(error_message), 422
        except Exception as e:
            error_message = {
                "errors": {
                    "product": {
                        "code": "server-error",
                        "name": "Erreur interne du serveur lors de la création de la commande.",
                        "details": str(e)
                    }
                }
            }
            return jsonify(error_message), 500



def calculate_shipping_price(order):
    total_weight = sum(order_product.product.weight * order_product.quantity for order_product in OrderProductsRow.select().where(OrderProductsRow.order == order))

    if total_weight <= 500:
        return 5
    elif 500 < total_weight <= 2000:
        return 10
    else:
        return 25







# Fonction de paiement asynchrone
def process_payment(order_id, total_price, shipping_price, credit_card_info):
    with app.app_context():
        order = OrdersRow.get(OrdersRow.orderid == order_id)

        # Log les paramètres de la fonction
        app.logger.debug(f"Processing payment for order {order_id} with total price {total_price} and shipping price {shipping_price} and credit card info {credit_card_info}")

        
        # Create a new dictionary for the API request
        api_request = {
            "credit_card": credit_card_info,
            "amount_charged": total_price + shipping_price
        }
        response = requests.post("http://dimprojetu.uqac.ca/~jgnault/shops/pay/", json=api_request)
        # Get the JSON response from the API
        api_response = response.json()
        app.logger.debug(f"API response: {api_response}")

        if response.status_code != 200:
            
            error_message = json.loads(response.text)
            app.logger.debug(f"Payment failed: {error_message}")
            order.debug = json.dumps(error_message)
            order.save()
            return jsonify({"errors": error_message["errors"]}), 422
        
        # Si le paiement est réussi, mettez à jour les détails de la commande dans Redis
        # Enregistrement de la transaction
        order.transaction = json.dumps(api_response["transaction"])
        app.logger.debug(f"Transaction saved: {order.transaction}")
        order.debug = json.dumps(api_response)
        order.paid = True
        order.save()

        
        updated_order_data = {
            'order': {
                'id': order.orderid,
                'total_price': total_price,
                'email': order.email if order.email else None,
                'credit_card': json.loads(order.credit_card) if order.credit_card else {},
                'shipping_information': json.loads(order.shipping_information) if order.shipping_information else {},
                'paid': True,
                'transaction': api_response.get("transaction", {}),
                'products': [
                    {
                        'id': order_product.product.id,
                        'quantity': order_product.quantity,
                        'name': order_product.product.name,
                        'price': order_product.product.price
                    }
                    for order_product in order.order_products
                ],
                'shipping_price': shipping_price
            }
        }

        # Mettez à jour les données en cache dans Redis
        redis.set(f'order:{order.orderid}', json.dumps(updated_order_data))

        return jsonify({
            'order': {
                'id': order.orderid,
                'total_price': total_price,
                'email': order.email if order.email else None,
                'credit_card': json.loads(order.credit_card) if order.credit_card else {},
                'shipping_information': json.loads(order.shipping_information) if order.shipping_information else {},
                'paid': True,
                'transaction': api_response.get("transaction", {}),
                'shipping_price': shipping_price
            }
        }), 200


@app.route("/order/<int:identifier>", methods=["GET", "PUT"])
def order_route(identifier: int):
    # Vérifier d'abord si la commande est en cache dans Redis
    cached_order = redis.get(f'order:{identifier}')
    if cached_order:
        return jsonify(json.loads(cached_order)), 200
    
    if request.method == "GET":
        try:
            order = OrdersRow.get(OrdersRow.orderid == identifier)
            order_products = OrderProductsRow.select().where(OrderProductsRow.order == order)

            total_price = order.total_price
            shipping_price = calculate_shipping_price(order)

            order_data = {
                'order': {
                    'id': order.orderid,
                    'total_price': total_price,
                    'email': order.email if order.email else None,
                    'credit_card': json.loads(order.credit_card) if order.credit_card else {},
                    'shipping_information': json.loads(order.shipping_information) if order.shipping_information else {},
                    'paid': order.paid,
                    'transaction': json.loads(order.transaction) if order.transaction else {},
                    'products': [
                        {
                            'id': order_product.product.id,
                            'quantity': order_product.quantity,
                            'name': order_product.product.name,
                            'price': order_product.product.price
                        }
                        for order_product in order_products
                    ],
                    'shipping_price': shipping_price,
                    'debug': order.debug if order.debug else {}
                }
            }

            #  Rendre le template Jinja avec les données de la commande
            return render_template("order.html", order=order_data)
        except OrdersRow.DoesNotExist:
            return jsonify({"error": "Commande non trouvée."}), 404
        

    elif request.method == "PUT":
        try:
            order = OrdersRow.get(OrdersRow.orderid == identifier)
            order_products = OrderProductsRow.select().where(OrderProductsRow.order == order)

            total_price = sum(order_product.product.price * order_product.quantity for order_product in order_products)
            total_weight = sum(order_product.product.weight * order_product.quantity for order_product in order_products)
            
            shipping_price = calculate_shipping_price(order)

            if "order" in request.json and "credit_card" in request.json:
                return jsonify({"error": "Ces deux appels doivent être faits de manière distincte."}), 400

            if "order" in request.json:
                # Vérifiez et mettez à jour les informations de livraison si elles sont fournies
                if "shipping_information" in request.json["order"] and "email" in request.json["order"]:
                    order.email = request.json["order"]["email"]
                    shipping_info = request.json["order"]["shipping_information"]
                    required_fields = ["country", "address", "postal_code", "city", "province"]
                    if all(field in shipping_info for field in required_fields):
                        order.shipping_information = json.dumps(shipping_info)
                    else:
                        return jsonify({"error": "Tous les champs des informations d'achats sont requis."}), 400
                else:
                    return jsonify({"error": "Les informations d'achats sont requises."}), 400
                
            if "credit_card" in request.json and order.paid is True:
                return jsonify({"error": "La commande a déjà été payée."}), 400

            if "credit_card" in request.json and order.paid is False:
                if not order.email:
                    return jsonify({"error": "L'email est obligatoire."}), 400
                order.credit_card = json.dumps(request.json["credit_card"])
                credit_card = request.json["credit_card"]
                
                # requête à l'API de paiement
                #response = requests.post("http://dimprojetu.uqac.ca/~jgnault/shops/pay/", json=api_request)

                # Ajouter le travail de paiement à la file d'attente RQ
                job = queue.enqueue(process_payment, order.orderid, total_price, shipping_price, credit_card)

                # Récupérer la liste des tâches dans la queue
                tasks = queue.jobs

                # Créer une liste pour stocker les détails de chaque tâche
                task_details = []
                for task in tasks:
                    task_detail = {
                        "id": task.id,
                        "func_name": task.func_name,
                        "args": task.args,
                        "status": task.get_status()
                    }
                    task_details.append(task_detail)

                # Renvoyer un code HTTP 202 avec les détails des tâches dans la réponse JSON
                return jsonify({"message": "Accepted", "tasks": task_details}), 202
            order.save()
            # Retournez les détails de la commande une fois que le paiement est terminé
            return jsonify({
                'order': {
                    'id': order.orderid,
                    'total_price': total_price,
                    'email': order.email if order.email else None,
                    'credit_card': json.loads(order.credit_card) if order.credit_card else {},
                    'shipping_information': json.loads(order.shipping_information) if order.shipping_information else {},
                    'paid': order.paid,
                    'transaction': json.loads(order.transaction) if order.transaction else {},
                    'shipping_price': shipping_price
                }
            }), 200
        except OrdersRow.DoesNotExist:
            return jsonify({"error": "Commande non trouvée."}), 404
        except ProductsRow.DoesNotExist:
            return jsonify({"error": "Produit non trouvé."}), 404
                

@click.command("init-db")
@with_appcontext
def init_db_command():
    db.connect()
    db.drop_tables([OrdersRow, ProductsRow, OrderProductsRow])
    db.create_tables([OrdersRow, ProductsRow, OrderProductsRow])
    print("Initialized the database.")
    initialize_products()
    print("Initialized the products.")

app.cli.add_command(init_db_command)

if __name__ == "__main__":
    os.environ["FLASK_DEBUG"] = "True"
    app.run()

    with Connection(redis):
        worker = Worker(map(Queue, listen))
        worker.work()




#template jinja https://jinja.palletsprojects.com/en/3.1.x/ pour le projet 1.
#exemple de jinja https://realpython.com/primer-on-jinja-templating/
#voir docker par la suite pour le projet numéro 2.
 



