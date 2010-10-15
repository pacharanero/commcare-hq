from django.http import HttpResponse
from corehq.util.webutils import render_to_response
from BeautifulSoup import BeautifulStoneSoup
from datetime import datetime

from .models import Application, Module, Form, XForm
from corehq.apps.new_xforms.forms import NewXFormForm, NewAppForm, NewModuleForm, ModuleConfigForm

from corehq.apps.domain.decorators import login_and_domain_required

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse, resolve
from corehq.apps.new_xforms.models import Domain
from StringIO import StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from urllib2 import urlopen
from django.conf import settings
from django.contrib.sites.models import Site
from django.views.static import serve
from corehq.apps.remote_apps.models import RemoteApp


DETAIL_TYPES = ('case_short', 'case_long', 'ref_short', 'ref_long')


@login_and_domain_required
def back_to_main(req, domain, app_id='', module_id='', form_id='', edit=False, **kwargs):
    params = {}
    if edit:
        params['edit'] = 'true'
    args = [domain]
    print "module_id: %s" % module_id
    for x in app_id, module_id, form_id:
        if x != '':
            args.append(x)
        else:
            break
    def urlize(params):
        if params:
            return '?' + ';'.join(["%s=%s" % (key,val) for key,val in params.items()])
        else:
            return ""
    view_name = ('forms', 'app_view', 'module_view', 'form_view')[len(args)-1]
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.%s' % view_name, args=args)
        + urlize(params)
    )
def _forms_context(req, domain, app_id='', module_id='', form_id='', select_first=False):
    #print "%s > %s > %s > %s " % (domain, app_id, module_id, form_id)
    edit = (req.GET.get('edit', '') == 'true')
    lang = req.GET.get('lang',
       req.COOKIES.get('lang', 'default')
    )

    applications = Application.view('new_xforms/applications', startkey=[domain], endkey=[domain, {}]).all()
    applications += RemoteApp.view('remote_apps/by_domain', key=domain).all()
    app = module = form = None
    if app_id:
        app = Domain(domain).get_app(app_id)
    elif applications and select_first:
        app = applications[0]
    if module_id:
        module = app.get_module(module_id)
    elif app and app.modules and select_first:
        module = app.get_module(0)
    if form_id:
        form = module.get_form(form_id)
    elif module and module['forms'] and select_first:
        form = module.get_form(0)
    xform = ""
    xform_contents = ""
    try:
        xform = XForm.get(form['xform_id'])
    except:
        pass
    if xform:
        #xform_contents = xform.fetch_attachment('xform.xml').encode('utf-8')
        #xform_contents, err, has_err = readable_form(xform_contents)
        xform_contents = ""

    return {
        'domain': domain,
        'applications': applications,

        'app': app,
        'module': module,
        'form': form,

        'xform': xform,
        'xform_contents': xform_contents,

        'new_app_form': NewAppForm(),
        'new_module_form': NewModuleForm(),
        'edit': edit,
        'langs': [lang] + (app.langs if app else [])    ,
        'lang': lang
    }
@login_and_domain_required
def forms(req, domain, app_id='', module_id='', form_id='', template='new_xforms/forms.html'):
    error = req.GET.get('error', '')
    context = _forms_context(req, domain, app_id, module_id, form_id)
    app = context['app']
    if not app and context['applications']:
        app_id = context['applications'][0]._id
        return back_to_main(**locals())

    force_edit = False
    if (not context['applications']) or (app and not app.modules):
        edit = True
        force_edit = True
    context.update({
        'force_edit': force_edit,
        'error':error,
        'app': app,
    })
    response = render_to_response(req, template, context)
    response.set_cookie('lang', context['lang'])
    return response

@login_and_domain_required
def form_view(req, domain, app_id, module_id, form_id, template="new_xforms/form_view.html"):
    return forms(req, domain, app_id, module_id, form_id, template=template)

@login_and_domain_required
def module_view(req, domain, app_id, module_id, template='new_xforms/module_view.html'):
    return forms(req, domain, app_id, module_id, template=template)

@login_and_domain_required
def app_view(req, domain, app_id, template="new_xforms/app_view.html"):
    return forms(req, domain, app_id, template=template)

@login_and_domain_required
def new_app(req, domain):
    lang = 'default'
    if req.method == "POST":
        form = NewAppForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            name = cd['name']
            if " (remote)" == name[-9:]:
                name = name[:-9]
                doc_type = "RemoteApp"
            else:
                doc_type = "Application"


            all_apps = Application.view('new_xforms/applications', key=[domain]).all()
            if name in [a.name.get(lang, "") for a in all_apps]:
                error="app_exists"
            else:
                if doc_type == "Application":
                    app = Application(domain=domain, modules=[], name={lang: name}, langs=["default"])
                else:
                    app = RemoteApp(domain=domain, name={lang: name}, langs=["default"])
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app['_id']])
                    + "?edit=true"
                )

        else:
            error="app_form_invalid"
    else:
        error="wtf"
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain])
        + "?edit=true" + ";error=%s" % error
    )

@login_and_domain_required
def new_module(req, domain, app_id):
    lang = req.COOKIES.get('lang', 'default')
    if req.method == "POST":
        form = NewModuleForm(req.POST)
        if form.is_valid():
            cd = form.cleaned_data
            name = cd['name']
            app = Domain(domain).get_app(app_id)
            if name in [m['name'].get(lang, "") for m in app.modules]:
                error = "module_exists"
            else:
                module_id = len(app.modules)
                app.modules.append({
                    'name': {lang: name},
                    'forms': [],
                    'case_type': '',
                    'case_name': {},
                    'ref_name': {},
                    'details': [{'type': detail_type, 'columns': []} for detail_type in DETAIL_TYPES],
                })
                app.save()
                return HttpResponseRedirect(
                    reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
                    + "?edit=true"
                )
        else:
            error = "module_form_invalid"
    else:
        error = "wtf"

    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app_id])
        + "?edit=true" + ";error=%s" % error
    )

@login_and_domain_required
def new_form(req, domain, app_id, module_id, template="new_xforms/new_form.html"):
    lang = req.COOKIES.get('lang', 'default')
    if req.method == "POST":
        form = NewXFormForm(req.POST, req.FILES)

        if form.is_valid():
            cd = form.cleaned_data
            name = cd['name']
            doc = _register_xform(
                attachment=cd['file'],
                display_name=name,
                domain=domain
            )
            context = _forms_context(req, domain, app_id, module_id, select_first=False)
            # module and form are not copies, so modifying them modifies app
            form = {
                'name': {lang: cd['name']},
                'xform_id': doc['_id'],
                'xmlns': doc['xmlns']
            }
            if context['form']:
                context['form'].update(form)
                form_id = context['form'].id
            else:
                form_id = len(context['module']['forms'])
                context['module']['forms'].append(form)
            context['app'].save()
            return HttpResponseRedirect(
                reverse('corehq.apps.new_xforms.views.form_view', args=[domain, app_id, module_id, form_id])
                + "?edit=true"
            )

    context = _forms_context(req, domain, app_id, module_id)
    form_name = req.GET.get('form_name', '')
    context.update({
        'new_xform_form': NewXFormForm(initial={'name':form_name}),
        'edit': True,
        'view_name': "new_form"
    })
    return render_to_response(req, template, context)

@login_and_domain_required
def delete_app(req, domain, app_id):
    Domain(domain).get_app(app_id).delete()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.forms', args=[domain])
        + "?edit=true"
    )

@login_and_domain_required
def delete_module(req, domain, app_id, module_id):
    app = Domain(domain).get_app(app_id)
    del app.modules[int(module_id)]
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app_id])
        + "?edit=true"
    )

@login_and_domain_required
def delete_form(req, domain, app_id, module_id, form_id):
    app = Domain(domain).get_app(app_id)
    module = Module(app, module_id)
    del module['forms'][int(form_id)]
    app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.app_view', args=[domain, app_id])
        + "?edit=true"
    )


def _register_xform(display_name, attachment, domain):
    if not isinstance(attachment, basestring):
        attachment = attachment.read()
    doc = XForm()
    doc.display_name = display_name
    soup = BeautifulStoneSoup(attachment)
    doc.xmlns = soup.find('instance').findChild()['xmlns']

    doc.submit_time = datetime.utcnow()
    doc.domain = domain

    doc.save()
    doc.put_attachment(attachment, 'xform.xml', content_type='text/xml')
    return doc

@login_and_domain_required
def edit_module_attr(req, domain, app_id, module_id, attr):
    lang = req.COOKIES.get('lang', 'default')
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        module = app.get_module(module_id)
        if   "case_type" == attr:
            case_type = req.POST.get("case_type", None)
            module['case_type'] = case_type
        elif ("name", "case_name", "ref_name").__contains__(attr):
            name = req.POST.get(attr, None)
            module[attr][lang] = name
        app.save()
    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
        + "?edit=true"
    )
@login_and_domain_required
def edit_module_detail(req, domain, app_id, module_id):
    lang = req.COOKIES.get('lang', 'default')
    if req.method == "POST":
        column_id = int(req.POST.get('column_id', -1))
        detail_type = req.POST.get('detail_type', '')

        assert(detail_type in DETAIL_TYPES)

        column = dict((key, req.POST[key]) for key in ('header', 'model', 'field', 'format', 'enum'))
        app = Domain(domain).get_app(app_id)
        module = app.get_module(module_id)

        def _enum_to_dict(enum):
            if not enum:
                return {}
            answ = {}
            for s in enum.split(','):
                key, val = (x.strip() for x in s.strip().split('='))
                answ[key] = {}
                answ[key][lang] = val
            return answ
            #return dict((y.strip() for y in x.strip().split('=')) for x in enum.split(',')) if enum else {}

        column['enum'] = _enum_to_dict(column['enum'])
        column['header'] = {lang: column['header']}
        for detail in module['details']:
            if detail['type'] == detail_type:
                break
        if detail['type'] != detail_type:
            detail = {'type': detail_type}
            module['details'].append(detail)


        if(column_id == -1):
            detail['columns'].append(column)
        else:
            realcol = detail['columns'][column_id]
            for key in ('model', 'field', 'format'):
                realcol[key] = column[key]

            realcol['header'][lang] = column['header'][lang]

            for key in column['enum']:
                realcol['enum'][key][lang] = column['enum'][key][lang]
        app.save()

    return HttpResponseRedirect(
        reverse('corehq.apps.new_xforms.views.module_view', args=[domain, app_id, module_id])
        + "?edit=true"
    )

@login_and_domain_required
def delete_module_detail(req, domain, app_id, module_id):
    if req.method == "POST":
        column_id = int(req.POST['column_id'])
        detail_type = req.POST['detail_type']
        app = Domain(domain).get_app(app_id)
        module = app.get_module(module_id)
        for detail in module['details']:
            if detail['type'] == detail_type:
                del detail['columns'][column_id]
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def edit_form_attr(req, domain, app_id, module_id, form_id, attr):
    lang = req.COOKIES.get('lang', 'default')
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        form = app.get_module(module_id).get_form(form_id)
        if   "requires" == attr:
            requires = req.POST['requires']
            form['requires'] = requires
        elif "name" == attr:
            name = req.POST['name']
            form['name'][lang] = name
        elif "xform" == attr:
            xform = req.FILES['xform']
            doc = _register_xform(
                display_name="",
                attachment=xform,
                domain=domain
            )
            form['xform_id'] = doc['_id']
            form['xmlns'] = doc['xmlns']
        elif "show_count" == attr:
            show_count = req.POST['show_count']
            form['show_count'] = True if show_count == "True" else False

        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def edit_app_lang(req, domain, app_id):
    if req.method == "POST":
        lang = req.POST['lang']
        lang_id = int(req.POST.get('lang_id', -1))
        app = Domain(domain).get_app(app_id)
        if lang_id == -1:
            app.langs.append(lang)
        else:
            app.langs[lang_id] = lang
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def delete_app_lang(req, domain, app_id):
    if req.method == "POST":
        lang_id = int(req.POST['lang_id'])
        app = Domain(domain).get_app(app_id)
        del app.langs[lang_id]
        app.save()
    return back_to_main(edit=True, **locals())

@login_and_domain_required
def edit_app_attr(req, domain, app_id, attr):
    lang = req.COOKIES.get('lang', 'default')
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        if   "suite_url" == attr:
            if app.doc_type not in ("RemoteApp",):
                raise Exception("App type %s does not support suite urls" % app.doc_type)
            app['suite_url'] = req.POST['suite_url']
            app.save()
    return back_to_main(edit=True, **locals())


@login_and_domain_required
def swap(req, domain, app_id, key):
    if req.method == "POST":
        app = Domain(domain).get_app(app_id)
        i, j = (int(x) for x in (req.POST['to'], req.POST['from']))
        assert(i < j)
        if   "forms" == key:
            module_id = int(req.POST['module_id'])
            forms = app.modules[module_id]['forms']
            forms.insert(i, forms.pop(j))
            # I didn't think I'd have to do this, but it makes it work...
            app.modules[module_id]['forms'] = forms
        elif "modules" == key:
            modules = app.modules
            modules.insert(i, modules.pop(j))
            app.modules = modules
        elif "detail" == key:
            module_id = int(req.POST['module_id'])
            detail_type = req.POST['detail_type']
            module = app.get_module(module_id)
            detail = module['details'][DETAIL_TYPES.index(detail_type)]
            columns = detail['columns']
            columns.insert(i, columns.pop(j))
            detail['columns'] = columns
        elif "langs" == key:
            langs = app.langs
            langs.insert(i, langs.pop(j))
            app.langs = langs
        app.save()
    return back_to_main(edit=True, **locals())

def _url_base():
    return 'http://%s' % Site.objects.get(id = settings.SITE_ID).domain

def _check_domain_app(domain, app_id):
    Domain(domain).get_app(app_id)

def download_profile(req, domain, app_id, template='new_xforms/profile.xml'):
    app = Domain(domain).get_app(app_id)
    url_base = _url_base()
    post_url = url_base + reverse('corehq.apps.receiver.views.post', args=[domain])
    if 'suite_url' in app and app['suite_url']:
        suite_url = app['suite_url']
    else:
        suite_url = url_base + reverse('corehq.apps.new_xforms.views.download_suite', args=[domain, app_id])
    return render_to_response(req, template, {
        'suite_url': suite_url,
        'post_url': post_url,
        'post_test_url': post_url,
    })

def download_suite(req, domain, app_id, template='new_xforms/suite.xml'):
    app = Domain(domain).get_app(app_id)
    return render_to_response(req, template, {
        'app': app
    })


def download_app_strings(req, domain, app_id, lang, template='new_xforms/app_strings.txt'):
    app = Domain(domain).get_app(app_id)
    return render_to_response(req, template, {
        'app': app,
        'langs': [lang] + app.langs,
    })

def download_xform(req, domain, app_id, module_id, form_id):
    xform_id = Domain(domain).get_app(app_id).get_module(module_id).get_form(form_id)['xform_id']
    xform = XForm.get(xform_id)
    xform_xml = xform.fetch_attachment('xform.xml')
    return HttpResponse(xform_xml)

def download_jad(req, domain, app_id, template="new_xforms/CommCare.jad"):
    app = Domain(domain).get_app(app_id)
    url_base = _url_base()
    if 'profile_url' in app and app['profile_url']:
        profile_url = app['profile_url']
    else:
        profile_url = url_base + reverse('corehq.apps.new_xforms.views.download_profile', args=[domain, app_id])
    response = render_to_response(req, template, {
        'domain': domain,
        'app': app,
        'profile_url': profile_url,
        'jar_url': url_base + reverse('corehq.apps.new_xforms.views.download_jar', args=[domain, app_id]),
    })
    response["Content-Type"] = "text/vnd.sun.j2me.app-descriptor"
    return response

def download_jar(req, domain, app_id):
    view,args,kwargs = resolve('/static/new_xforms/CommCare.jar')
    print view, args, kwargs
    response = view(req, *args, **kwargs)
    response['Content-Type'] = "application/java-archive"
    return response

#@login_and_domain_required
#def download(req, domain, app_id):
#    url_base = _url_base()
#    response = HttpResponse(mimetype="application/zip")
#    response['Content-Disposition'] = "filename=commcare_app.zip"
#    app = Domain(domain).get_app(app_id)
#    root = url_base + reverse('corehq.apps.new_xforms.views.download', args=[domain, app_id])
#    paths = ["profile.xml", "suite.xml"]
#    for lang in app.langs:
#        paths.append("%s/app_strings.txt" % lang)
#    for module in app.get_modules():
#        for form in module.get_forms():
#            paths.append("m%s/f%s.xml" % (module.id, form.id))
#    print paths
#    buffer = StringIO()
#    zipper = ZipFile(buffer, 'w', ZIP_DEFLATED)
#    for path in paths:
#        print path
#        zipper.writestr(path, urlopen(root + path).read())
#    zipper.close()
#    buffer.flush()
#    response.write(buffer.getvalue())
#    buffer.close()
#    return response

#http://bit.ly/bhZ3by