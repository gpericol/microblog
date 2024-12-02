from datetime import datetime
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, url_for, session
from flask_paginate import Pagination, get_page_args
from werkzeug.security import check_password_hash, generate_password_hash
from models import *
from forms import *
import markdown2
import bleach
from flask_wtf.csrf import CSRFProtect

# create the extension
app = Flask(__name__)

app.config['SECRET_KEY'] = 'Spread_Love'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
POSTS_PER_PAGE = 1

csrf = CSRFProtect(app)

db.init_app(app)

with app.app_context():
    db.create_all()

def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'Error in field "{getattr(form, field).label.text}": {error}', 'error')

@app.template_filter('markdown')
def markdown_to_html(markdown_text):
    safe_html = bleach.clean(markdown_text, tags=bleach.sanitizer.ALLOWED_TAGS, attributes=bleach.sanitizer.ALLOWED_ATTRIBUTES)
    safe_html = markdown2.markdown(safe_html)
    return safe_html

def check_role(required_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'id' not in session or 'role' not in session:
                flash('You must be logged in to access this page', 'error')
                return redirect(url_for('login'))
            elif session['role'] not in required_roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('login'))
            return func(*args, **kwargs)
        return wrapper
    return decorator    

@app.route('/install', methods=['GET'])
def install():
    existing_user = User.query.first()
    if not existing_user:
        admin_password_hash = generate_password_hash('admin')
        admin_user = User(username='admin', password=admin_password_hash, role='admin')
        db.session.add(admin_user)
        db.session.commit()
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'id' in session:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

#list all users
@app.route('/users', methods=['GET'])
@check_role(['admin'])
def users():
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/create_user', methods=['GET', 'POST'])
@check_role(['admin'])
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        password_hash = generate_password_hash(password)
        new_user = User(username=username, password=password_hash, role='user')
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('users'))
    else:
        flash_errors(form)
    return render_template('create_user.html', form=form)

@app.route('/change_password/<int:user_id>', methods=['GET', 'POST'])
@check_role(['admin'])
def change_password(user_id):
    user = User.query.get_or_404(user_id)
    form = ChangePasswordForm()
    if form.validate_on_submit():
        new_password = form.new_password.data
        user.password = generate_password_hash(new_password)
        db.session.commit()
        return redirect(url_for('users'))
    else:
        flash_errors(form)
    return render_template('change_password.html', form=form, user=user)


@app.route('/create_post', methods=['GET', 'POST'])
@check_role(['admin', 'user'])
def create_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        title = form.title.data
        content = form.content.data
        author_id = session.get('id')
        new_post = Post(title=title, content=content, author_id=author_id)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('index'))
    else:
        flash_errors(form)
    return render_template('create_post.html', form=form)

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@check_role(['admin', 'user'])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author_id != session.get('id') and session.get('role') != 'admin':
        return redirect(url_for('index'))

    form = CreatePostForm(obj=post)
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        return redirect(url_for('index'))
    else:
        flash_errors(form)
    return render_template('create_post.html', form=form, post=post)

@app.route('/delete_post/<int:post_id>', methods=['GET'])
@check_role(['admin'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()

    return redirect(url_for('index'))


@app.route('/', methods=['GET'])
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date.desc()).paginate(page=page, per_page=POSTS_PER_PAGE)
    pagination = Pagination(page=page, total=posts.total, per_page=POSTS_PER_PAGE, css_framework='bootstrap4')

    return render_template('index.html', posts=posts, pagination=pagination)


@app.route('/show_post/<int:post_id>', methods=['GET'])
def show_post(post_id):
    post = Post.query.get_or_404(post_id)
    formatted_date = post.date.strftime('%Y-%m-%d')
    return render_template('show_post.html', post=post, formatted_date=formatted_date)