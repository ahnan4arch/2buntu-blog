from calendar import timegm
from datetime import datetime
from hashlib import md5
from json import dumps, JSONEncoder, loads

from django.core.urlresolvers import reverse
from django.db.models import Count
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.shortcuts import render

from twobuntu.accounts.models import Profile
from twobuntu.articles.models import Article
from twobuntu.categories.models import Category

class APIException(Exception):
    """Base for all API exceptions."""

class ObjectEncoder(JSONEncoder):
    """JSON encoder for supported Django model instances."""

    def default(self, o):
        if type(o) is QuerySet: return list(o)
        elif type(o) is Article: return self._encode_article(o)
        elif type(o) is Category: return self._encode_category(o)
        elif type(o) is Profile: return self._encode_profile(o)
        else: return JSONEncoder.default(self, o)

    def _encode_article(self, article):
        """Encode an article."""
        return {
            'id': article.id,
            'title': article.title,
            'author': {
                'id': article.author.id,
                'name': unicode(article.author),
                'email_hash': md5(article.author.email).hexdigest(),
            },
            'category': {
                'id': article.category.id,
                'name': article.category.name,
            },
            'body': article.render(),
            'cc_license': article.cc_license,
            'date': timegm(article.date.utctimetuple()),
        }

    def _encode_category(self, category):
        """Encode a category."""
        return {
            'id': category.id,
            'name': category.name,
            'articles': category.num_articles,
        }

    def _encode_profile(self, profile):
        """Encode a profile."""
        return {
            'id': profile.user.id,
            'name': unicode(profile),
            'email_hash': md5(article.author.email).hexdigest(),
            'age': profile.age(),
            'location': profile.location,
            'website': profile.website,
            'bio': profile.bio,
            'last_seen': timegm(profile.user.last_login.utctimetuple()),
        }

def endpoint(fn):
    """Wrap the API endpoint."""
    def wrapper(request, **kwargs):
        try:
            json = dumps(fn(request, **kwargs), cls=ObjectEncoder)
        except APIException as e:
            json = dumps({
                'error': str(e),
            })
        if 'debug' in request.GET:
            return render(request, 'api/debug.html', {
                'title': '2buntu API Debugger',
                'parent':  {
                    'title': 'API',
                    'url':   reverse('api:index'),
                },
                'json': dumps(loads(json), indent=4),
            })
        elif 'callback' in request.GET:
            return HttpResponse('%s(%s)' % (request.GET['callback'], json,),
                                content_type='application/javascript')
        else:
            return HttpResponse(json, content_type='application/json')
    return wrapper

def paginate(fn):
    """Limit the number of items returned."""
    def wrapper(request, **kwargs):
        try:
            page = max(int(request.GET['page']), 1) if 'page' in request.GET else 1
            size = min(max(int(request.GET['size']), 0), 20) if 'size' in request.GET else 20
        except ValueError:
            raise APIException("Invalid page and/or size parameter specified.")
        return fn(request, **kwargs)[(page - 1) * size:page * size]
    return wrapper

def minmax(fn):
    """Process minimum and maximum parameters."""
    def wrapper(request, **kwargs):
        filters = {}
        try:
            if 'min' in request.GET: filters['date__gte'] = datetime.fromtimestamp(int(request.GET['min']))
            if 'max' in request.GET: filters['date__lte'] = datetime.fromtimestamp(int(request.GET['max']))
        except ValueError:
            raise APIException("Invalid min and/or max parameter specified.")
        return fn(request, **kwargs).filter(**filters)
    return wrapper

@endpoint
@paginate
@minmax
def articles(request):
    """Return all recent articles."""
    return Article.objects.filter(status=Article.PUBLISHED)

@endpoint
@paginate
@minmax
def article_by_id(request, id):
    """Return the specified article."""
    return Article.objects.filter(pk=id, status=Article.PUBLISHED)

@endpoint
@paginate
@minmax
def authors(request):
    """Return most popular authors."""
    return Profile.objects.all()

@endpoint
@paginate
@minmax
def author_by_id(request, id):
    """Return the specified author."""
    return Profile.objects.filter(pk=id)

@endpoint
@paginate
@minmax
def articles_by_author(request, id):
    """Return articles written by the specified author."""
    return Article.objects.filter(author=id, status=Article.PUBLISHED)

@endpoint
@paginate
@minmax
def categories(request):
    """Return most popular categories."""
    return Category.objects.all().annotate(num_articles=Count('article'))

@endpoint
@paginate
@minmax
def articles_by_category(request, id):
    """Return recent articles in the specified category."""
    return Article.objects.filter(category=id, status=Article.PUBLISHED)