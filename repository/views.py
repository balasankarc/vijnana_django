import os
import random
from datetime import datetime

import bcrypt
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.files.images import get_image_dimensions
from django.db import IntegrityError
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render
from openpyxl import load_workbook
from PIL import Image
from pylatex import Document, Package

from .forms import (AssignOrRemoveStaffForm, EditProfileForm, NewResourceForm,
                    NewSubjectForm, ProfilePictureCropForm,
                    ProfilePictureUploadForm, QuestionBankUploadForm,
                    QuestionPaperCategoryForm, QuestionPaperGenerateForm,
                    SearchForm, SignInForm, SignUpForm)
from .models import (Department, Exam, Profile, Question, Resource, Subject,
                     User)

RESOURCE_TYPES = {
    'Presentation': 'presentation',
    'Paper Publication': 'paper_publication',
    'Subject Note': 'subject_note',
    'Project Thesis': 'project_thesis',
    'Seminar Report': 'seminar_report',
    'Previous Question Paper': 'previous_question_paper'
}

USER_STATUS = ['student', 'faculty', 'labstaff', 'administrator', 'hod']


def current_user(request):
    if 'user' in request.session:
        return User.objects.get(username=request.session['user'])
    else:
        return None


def is_user_hod(request, subject):
    user = current_user(request)
    if user.status == 'hod' and user.department == subject.department:
        return True
    else:
        return False


def home(request):
    """Displays home page"""
    user = current_user(request)
    if user:
        return render(request, 'profile.html', {'user': user})
    else:
        return render(request, 'home.html')


def user_signin(request):
    """Handles user's sign in action"""
    error = ""
    username = ""
    if request.POST:
        form = SignInForm(request.POST)
        if form.is_valid():
            input_username = form.cleaned_data['username']
            input_password = form.cleaned_data['password'].encode('utf-8')
            try:
                user = User.objects.get(username=input_username)
                username = user.username
                password = user.password.encode('utf-8')
                if bcrypt.hashpw(input_password, password) == password:
                    request.session['user'] = username
                    request.session['usertype'] = user.status
                    return HttpResponseRedirect('/')
                else:
                    raise ObjectDoesNotExist
            except ObjectDoesNotExist:
                error = "Incorrect username or password"
    else:
        if 'user' in request.session.keys():
            # If user already logged in, redirect to homepage
            return HttpResponseRedirect('/')
    return render(request, 'signin.html',
                  {'error': error, 'username': username})


def user_signout(request):
    """Handles user's sign out action"""
    if 'user' in request.session.keys():
        del request.session['user']
        del request.session['usertype']
    return HttpResponseRedirect('/')


def user_signup(request):
    """Handles user's sign up action"""
    department_list = Department.objects.all()
    error = ""
    if request.POST:
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                input_username = form.cleaned_data['username']
                input_password = form.cleaned_data['password'].encode('utf-8')
                input_name = form.cleaned_data['fullname']
                input_department = form.cleaned_data['department']
                password_hash = bcrypt.hashpw(input_password, bcrypt.gensalt())
                user = User(username=input_username,
                            password=password_hash,
                            name=input_name,
                            department_id=input_department)
                user.save()
                request.session['user'] = input_username
                request.session['usertype'] = user.status
                return HttpResponseRedirect('/')
            except IntegrityError:
                error = error + "Username already in use"
    else:
        if 'user' in request.session.keys():
            # If user already logged in, redirect to homepage
            return HttpResponseRedirect('/')
    return render(request, 'signup.html',
                  {'error': error, 'department_list': department_list})


def new_resource(request):
    """Add a new resource"""
    subject_list = Subject.objects.all()
    error = ""
    if request.POST:
        print request.POST
        form = NewResourceForm(request.POST, request.FILES)
        print form
        if form.is_valid():
            try:
                input_title = form.cleaned_data['title']
                input_category = form.cleaned_data['category']
                input_subject = Subject.objects.get(
                    id=form.cleaned_data['subject'])
                resource_uploader = User.objects.get(
                    username=request.session['user'])
                input_file = request.FILES['resourcefile']
                resource = Resource(
                    title=input_title, category=input_category,
                    subject=input_subject, resourcefile=input_file,
                    uploader=resource_uploader)
                resource.save()
                return HttpResponseRedirect('/resource/' + str(resource.id))
            except Exception, e:
                error = e
                print error
    return render(request, 'newresource.html',
                  {
                    'error': error,
                    'subject_list': subject_list,
                    'type_list': RESOURCE_TYPES
                  })


def get_resource(request, resource_id):
    """Get details about a single resource"""
    try:
        resource = Resource.objects.get(id=resource_id)
        return render(request, 'resource.html', {'resource': resource})
    except ObjectDoesNotExist:
        return render(request, 'error.html',
                      {
                          'error': 'The requested resource not found.'
                      }, status=404)


def type_resource_list(request, type_name):
    """Get all resources of a specific type"""
    try:
        type_name = type_name.replace('_', ' ')
        resources = Resource.objects.filter(category=RESOURCE_TYPES[type_name])
        if resources:
            return render(request, 'type_resource_list.html',
                          {
                              'resource_list': resources,
                              'type': type_name
                          })
        else:
            raise ObjectDoesNotExist
    except ObjectDoesNotExist:
        return render(request, 'error.html',
                      {
                          'error': 'No resources under the requested category'
                      }, status=404)


def search(request):
    """Search for resources having a specific query in their title"""
    if request.POST:
        try:
            form = SearchForm(request.POST)
            if form.is_valid():
                query = form.cleaned_data['query']
                resource_list = Resource.objects.filter(title__contains=query)
                if resource_list:
                    return render(request, 'search.html',
                                  {
                                      'resource_list': resource_list,
                                      'query': query
                                  })
                else:
                    raise ObjectDoesNotExist
        except ObjectDoesNotExist:
            return render(request, 'error.html',
                          {
                              'error': 'Searched returned no resources.'
                          }, status=404)
    else:
        return render(request, 'search.html')


def my_subjects(request, username):
    user = current_user(request)
    if user:
        if user.status == 'teacher' or user.status == 'hod':
            subject_list = user.teachingsubjects.all()
        else:
            subject_list = user.subscribedsubjects.all()
        if subject_list:
            return render(request, 'my_subjects.html',
                          {
                              'subject_list': subject_list,
                          })
        else:
            return render(request, 'error.html',
                          {
                              'error': 'You are not subscribed to any subjects'
                          }, status=404)
    else:
        return render(request, 'error.html',
                      {
                          'error': 'You are not logged in.'
                      }, status=404)


def view_subject(request, subject_id):
    try:
        subject = Subject.objects.get(id=subject_id)
        resource_list = subject.resource_set.all()
        subscription_status = True
        is_hod = False
        has_staff = False
        is_staff = False
        subject_staff_list = subject.staff.all()
        if subject_staff_list:
            has_staff = True
        if 'user' in request.session:
            user = current_user(request)
            if subject not in user.subscribedsubjects.all():
                subscription_status = False
            if user.status == 'hod' and user.department == subject.department:
                is_hod = is_user_hod(request, subject)
            if user in subject.staff.all():
                is_staff = True
        return render(request, 'subject_resource_list.html',
                      {
                          'subject': subject,
                          'resource_list': resource_list,
                          'subscription_status': subscription_status,
                          'is_hod': is_hod,
                          'is_staff': is_staff,
                          'has_staff': has_staff,
                          'subject_staff_list': subject_staff_list
                      })
    except ObjectDoesNotExist:
        return render(request, 'error.html',
                      {
                          'error': 'The subject you requested does not exist.'
                      }, status=404)


def subscribe_me(request, subject_id):
    try:
        subject = Subject.objects.get(id=subject_id)
        subject.students.add(current_user(request))
        subject.save()
        return HttpResponseRedirect('/subject/' + subject_id)
    except ObjectDoesNotExist:
        return render(request, 'error.html',
                      {
                          'error': 'The subject you requested does not exist.'
                      }, status=404)


def unsubscribe_me(request, subject_id):
    try:
        subject = Subject.objects.get(id=subject_id)
        if 'user' in request.session:
            user = current_user(request)
            if user in subject.students.all():
                subject.students.remove(user)
                subject.save()
        return HttpResponseRedirect('/subject/' + subject_id)
    except ObjectDoesNotExist:
        return render(request, 'error.html',
                      {
                          'error': 'The subject you requested does not exist.'
                      }, status=404)


def assign_staff(request, subject_id):
    subject = Subject.objects.get(id=subject_id)
    is_hod = is_user_hod(request, subject)
    if request.POST and is_hod:
        try:
            form = AssignOrRemoveStaffForm(request.POST)
            if form.is_valid():
                for staff_id in form.cleaned_data['staffselect']:
                    staff = User.objects.get(id=staff_id)
                    subject.staff.add(staff)
        except Exception, e:
            print e
    else:
        staff_list = {}
        for department in Department.objects.all():
            staff_list[department.name] = [x for x in department.user_set.all()
                                           if x.status == 'teacher' or
                                           x.status == 'hod']
        return render(request, 'assign_staff.html',
                      {
                       'is_hod': is_hod,
                       'staff_list': staff_list,
                       'subject': subject
                      })
    return HttpResponseRedirect('/subject/' + subject_id)


def remove_staff(request, subject_id):
    subject = Subject.objects.get(id=subject_id)
    if 'user' in request.session:
        user = current_user(request)
        if user.status == 'hod' and user.department == subject.department:
            is_hod = True
    if request.POST:
        print "POST"
        try:
            form = AssignOrRemoveStaffForm(request.POST)
            if form.is_valid():
                for staff_id in form.cleaned_data['staffselect']:
                    staff = User.objects.get(id=staff_id)
                    subject.staff.remove(staff)
                    subject.save()
        except Exception, e:
            print e
    else:
        staff_list = subject.staff.all()
        print staff_list
        return render(request, 'remove_staff.html',
                      {
                       'is_hod': is_hod,
                       'staff_list': staff_list,
                       'subject': subject
                      })
    return HttpResponseRedirect('/subject/' + subject_id)


def new_subject(request):
    department_list = Department.objects.all()
    error = ''
    if request.POST:
        try:
            form = NewSubjectForm(request.POST)
            if form.is_valid():
                input_code = form.cleaned_data['code']
                input_name = form.cleaned_data['name']
                input_credit = form.cleaned_data['credit']
                input_course = form.cleaned_data['course']
                input_semester = form.cleaned_data['semester']
                input_department = current_user(request).department.id
                subject = Subject(code=input_code, name=input_name,
                                  credit=input_credit, course=input_course,
                                  semester=input_semester,
                                  department_id=input_department)
                subject.save()
                return HttpResponseRedirect('/subject/' + str(subject.id))
        except IntegrityError:
            error = 'Subject Code already exists'
    return render(request, 'new_subject.html',
                  {'department_list': department_list,
                   'error': error
                   })


def upload_profilepicture(request, username):
    user = User.objects.get(username=username)
    if not user:
        return render(request, 'error.html',
                      {
                       'error': 'The user you requested does not exist.'
                      }, status=404)
    elif user != current_user(request):
        return render(request, 'error.html',
                      {
                       'error': 'You are not permitted to do this.'
                      }, status=404)
    else:
        try:
            p = user.profile
        except:
            p = Profile(user_id=user.id)
            p.save()
        if request.POST:
            print "Post"
            print p.user.username
            form = ProfilePictureUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    image = request.FILES['image']
                    w, h = get_image_dimensions(image)
                    if w < 200 or h < 200 or w > 1000 or h > 1000:
                        error = """Image dimension should be between 500x500
                        and 1000x1000"""
                        raise
                    if p.picture:
                        os.remove(p.picture.path)
                    p.picture = image
                    p.save()
                    print p.picture.path
                    returnpath = '/user/' + \
                        user.username + '/crop_profilepicture'
                    return HttpResponseRedirect(returnpath)
                except:
                    return render(request, 'uploadprofilepicture.html',
                                  {'user': user, 'error': error})
            else:
                return render(request, 'uploadprofilepicture.html',
                              {'user': user})
        else:
            return render(request, 'uploadprofilepicture.html', {'user': user})
        return HttpResponseRedirect('/user/' + user.username)


def crop_profilepicture(request, username):
    user = User.objects.get(username=username)
    if not user:
        return render(request, 'error.html',
                      {
                       'error': 'The user you requested does not exist.'
                      }, status=404)
    elif user != current_user(request):
        return render(request, 'error.html',
                      {
                       'error': 'You are not permitted to do this.'
                      }, status=404)
    else:
        user = User.objects.get(username=username)
        if request.POST:
            if user.profile.picture:
                form = ProfilePictureCropForm(request.POST)
                if form.is_valid():
                    x1 = int(float(form.cleaned_data['x1']))
                    y1 = int(float(form.cleaned_data['y1']))
                    x2 = int(float(form.cleaned_data['x2']))
                    y2 = int(float(form.cleaned_data['y2']))
                    image = Image.open(user.profile.picture.path)
                    cropped_image = image.crop((x1, y1, x2, y2))
                    cropped_image.save(user.profile.picture.path)
                    return HttpResponseRedirect('/user/' + user.username)
                else:
                    print "Failure"
                    print form
            else:
                return HttpResponseRedirect('/user/' + user.username)
        else:
            return render(request, 'cropprofilepicture.html', {'user': user})


def profile(request, username):
    user = User.objects.get(username=username)
    return render(request, 'profile.html', {'user': user})


def edit_user(request, username):
    user = User.objects.get(username=username)
    current_name = user.name or ""
    current_address = user.profile.address or ""
    current_email = user.profile.email or ""
    current_bloodgroup = user.profile.bloodgroup or ""
    if request.POST:
        form = EditProfileForm(request.POST)
        try:
            if form.is_valid():
                print "Here"
                print form
                name = form.cleaned_data['name'] or ""
                address = form.cleaned_data['address'] or ""
                email = form.cleaned_data['email'] or ""
                bloodgroup = form.cleaned_data['bloodgroup'] or ""
                user.name = name
                p = user.profile
                p.address = address
                p.email = email
                p.bloodgroup = bloodgroup
                p.save()
                user.save()
                return HttpResponseRedirect('/user/'+user.username)
        except Exception, e:
            print e

    else:
        return render(request, 'edit.html',
                      {'user': user,
                       'current_name': current_name,
                       'current_address': current_address,
                       'current_email': current_email,
                       'current_bloodgroup': current_bloodgroup,
                       })


def read_excel_file(excelfilepath, subject):
    workbook = load_workbook(filename=excelfilepath)
    for row in workbook.worksheets[0].rows:
        try:
            questiontext = row[1].value
            print "Text", questiontext
            questionmodule = row[2].value
            questionmark = row[3].value
            question = Question(text=questiontext,
                                module=questionmodule,
                                mark=questionmark
                                )
            question.subject = subject
            question.save()
        except Exception, e:
            print "Error"
            print e
            pass


def upload_question_bank(request, subject_id):
    subject = Subject.objects.get(id=subject_id)
    if request.POST:
        form = QuestionBankUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                qbfile = request.FILES['qbfile']
                with open('/tmp/qb.xlsx', 'wb') as destination:
                    for chunk in qbfile.chunks():
                        destination.write(chunk)
                read_excel_file('/tmp/qb.xlsx', subject)
                return HttpResponseRedirect('/subject/'+subject_id)
            except:
                return render(request, 'upload_questionbank.html',
                              {'subject': subject,
                               'error': 'Some problem with the file'})
    else:
        return render(request, 'upload_questionbank.html',
                      {'subject': subject})


def select_random(itemlist, count):
    result = []
    N = 0
    for item in itemlist:
        N += 1
        if len(result) < count:
            result.append(item)
        else:
            s = int(random.random() * N)
            if s < count:
                result[s] = item
    return result


def make_pdf(subject, questions, exam, marks, time):
    print "Questions"
    print questions
    today = datetime.today()
    filename = subject.name.replace(' ', '_') + '_' + str(today.day) + str(today.month) + str(today.year)
    content = '''
    \\centering{\\Large{Adi Shankara Institute of Engineering and Technology, Kalady}} \\\\[.5cm]
    \\centering{\\large{%s}} \\\\[.5cm]
    \\centering{\\large{%s}} \\\\
    \\normalsize{Marks: %s \\hfill Time: %s Hrs}\\\\[.5cm]''' % (exam.name, subject.name, marks, time)
    for part in ['Part A', 'Part B', 'Part C']:
        if questions[part]:
            content = content + '\\centering{%s}\n' % part
            content = content + '\\begin{enumerate}\n'
            for mark in questions[part]:
                for question in questions[part][mark]:
                    text = question.text
                    if len(question.text) > 75:
                        print "Here", text
                        pos = text.index(' ', 70)
                        text = question.text[:pos] + '\\\\' + question.text[pos+1:]
                    content = content + '\\item{%s\\hfill%s}\n' % (text, question.mark)
            content = content + '\\end{enumerate}\n'
    print content
    doc = Document(default_filepath='/tmp/'+filename)
    doc.packages.append(Package('geometry', options=['tmargin=2.5cm',
                                                     'lmargin=2.5cm',
                                                     'rmargin=3.0cm',
                                                     'bmargin=2.0cm']))
    doc.append(content)
    doc.generate_pdf()
    qpinfile = open('/tmp/'+filename+'.pdf')
    qpfile = File(qpinfile)
    exam.questionpaper.save(filename+'.pdf', qpfile)
    return '/uploads/' + exam.questionpaper.url


def create_qp(subject, exam, totalmarks, time, question_criteria):
    questions = {'Part A': {}, 'Part B': {}, 'Part C': {}}
    status = 0
    for trio in question_criteria:
        module = trio[0]
        try:
            mark = int(trio[1])
        except:
            mark = float(trio[1])
        count = int(trio[2])
        questiontotallist = Question.objects.filter(module=module, mark=mark)
        selectedquestions = select_random(questiontotallist, count)
        if mark >= 7:
            part = 'Part C'
        elif mark >= 5:
            part = 'Part B'
        else:
            part = 'Part A'
        if mark not in questions[part]:
            questions[part][mark] = []
        questions[part][mark] = questions[part][mark] + selectedquestions
    if questions:
        for part in questions:
            for mark in questions[part]:
                for question in questions[part][mark]:
                    exam.question_set.add(question)
                    exam.save()
        status = 1
    path = make_pdf(subject, questions, exam, totalmarks, time)
    return status, path


def generate_question_paper(request, subject_id):
    error = ''
    subject = Subject.objects.get(id=subject_id)
    QuestionFormSet = formset_factory(QuestionPaperCategoryForm)
    if request.POST:
        print request.POST
        QPForm = QuestionPaperGenerateForm(request.POST)
        examname = ''
        totalmarks = ''
        time = ''
        if QPForm.is_valid():
            examname = QPForm.cleaned_data['examname']
            totalmarks = QPForm.cleaned_data['totalmarks']
            time = QPForm.cleaned_data['time']
            exam = Exam(name=examname, totalmarks=totalmarks, time=time,
                        subject_id=subject.id)
            exam.save()
        question_categories_set = QuestionFormSet(request.POST)
        if question_categories_set.is_valid():
            print "\n\n\n\n\n\n Form Data \n\n\n\n\n\n\n\n"
            question_criteria = []
            for form in question_categories_set.forms:
                if form.is_valid():
                    module = form.cleaned_data['module']
                    mark = form.cleaned_data['mark']
                    count = form.cleaned_data['count']
                    question_criteria.append((module, mark, count))
            status, path = create_qp(subject, exam, totalmarks,
                                     time, question_criteria)
            return HttpResponseRedirect(path)
        else:
            error = 'Choose some questions.'
    else:
        question_categories_set = QuestionFormSet()

    return render(request, 'generatequestionpaper.html',
                  {'subject': subject,
                   'qpformset': question_categories_set,
                   'error': error})
