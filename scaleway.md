# Déploiement Scaleway — architecture cible

1. Pousser ce dossier dans un dépôt GitHub privé `radar-projets-espacenova`.
2. Créer une base PostgreSQL managée Scaleway et récupérer sa chaîne de connexion SSL.
3. Construire l'image Docker depuis GitHub (ou via un registry).
4. Déployer l'image comme **Serverless Container** pour le dashboard.
5. Déployer la même image comme **Serverless Job** avec la commande :
   `python crawler.py --run-once`
6. Planifier le Job chaque jour (par exemple tôt le matin).
7. Définir `DATABASE_URL` sur le Container et le Job avec la même base PostgreSQL.
8. Ajouter ensuite le domaine `radar.espacenova.fr` et protéger l'accès.

Ne jamais mettre un mot de passe ou token dans GitHub. Utiliser les variables/secrets Scaleway.
