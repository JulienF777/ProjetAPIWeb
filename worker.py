# worker.py
import os
from flask import Flask, request, jsonify
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
from rq import Queue
import time
from rq import Worker, Queue, Connection
from app import redis  # Assurez-vous d'importer la connexion Redis depuis votre application Flask
from app import OrdersRow


# Configurer la connexion Redis
listen = ['default']
conn = redis.from_url("redis://cache:6379")

# Lancer le worker
if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()

