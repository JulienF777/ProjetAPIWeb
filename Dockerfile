# Utilisez une image Python officielle en tant qu'image parent
FROM python:3.7-buster

# Définition du répertoire de travail
WORKDIR /app

# Copiez le fichier actuel dans le conteneur au chemin de travail /app
COPY . .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Commande à exécuter à l'exécution du conteneur
#CMD ["python", "app.py"]
#CMD ["sh", "-c", "flask init-db && flask run --host=0.0.0.0 --port=5000"]

# Exposer le port sur lequel l'application Flask s'exécutera
EXPOSE 5000

# Exécuter le worker RQ
CMD ["python", "worker.py"]