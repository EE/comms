release: python manage.py migrate --no-input
postdeploy: python manage.py migrate --no-input
web: gunicorn comms.wsgi
