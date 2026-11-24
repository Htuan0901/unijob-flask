"""Launch script (FLASK_APP=unijob.py): tạo app, shell context."""
import os

import sqlalchemy as sa
import sqlalchemy.orm as so

from app import create_app, db
from app.models import (Application, Category, EmployerProfile, JobAlert, JobPost, Notification, Review,
                        StudentProfile, User)

app = create_app(os.environ.get('FLASK_CONFIG') or 'default')


@app.shell_context_processor
def make_shell_context():
    return dict(sa=sa, so=so, db=db, User=User, StudentProfile=StudentProfile, EmployerProfile=EmployerProfile,
                Category=Category, JobPost=JobPost, Application=Application, Review=Review,
                Notification=Notification, JobAlert=JobAlert)
