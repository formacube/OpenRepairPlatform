from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.core.exceptions import ValidationError
from django.views.generic import DetailView, ListView, FormView, CreateView, \
    UpdateView
from .models import *
from itsdangerous import URLSafeSerializer, BadData
from post_office import mail
from django.urls import reverse_lazy
from django.utils import timezone
from logging import getLogger
from django.template.loader import render_to_string

from django.forms import ModelForm, CharField, HiddenInput, ModelMultipleChoiceField, ModelChoiceField, CheckboxSelectMultiple, MultipleChoiceField
from datetimepicker.widgets import DateTimePicker
from rules.contrib.views import PermissionRequiredMixin

from django_markdown.fields import MarkdownFormField
from django_markdown.widgets import MarkdownWidget

from fm.views import AjaxCreateView, AjaxUpdateView

import datetime
from django import forms

logger = getLogger(__name__)



def homepage(request):
    events = PublishedEvent.objects.filter(
        starts_at__gte=timezone.now()).order_by('starts_at')[:10]
    context = {"events": events}
    return render(request, 'plateformeweb/home.html', context)



# TODO move all this in separate apps?

class OrganizationView(DetailView):
    model = Organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class OrganizationListView(ListView):
    model = Organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["list_type"] = "organization"
        return context


# --- edit ---

class OrganizationFormView():
    model = Organization
    fields = ["name", "description", "active"]

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = super().get_form(form_class)
        form.fields['description'] = CharField(widget=MarkdownWidget())
        return form


    def get_success_url(self):
        return reverse_lazy('organization_detail',
                            args=(self.object.pk, self.object.slug,))


class OrganizationCreateView(PermissionRequiredMixin, OrganizationFormView,
                             CreateView):
    permission_required = 'plateformeweb.create_organization'


class OrganizationEditView(PermissionRequiredMixin, OrganizationFormView,
                           AjaxUpdateView):
    permission_required = 'plateformeweb.edit_organization'
    queryset = Organization.objects


# --- Places ---

class PlaceView(DetailView):
    model = Place

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class PlaceListView(ListView):
    model = Place

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["list_type"] = "place"
        return context


# --- edit ---

class PlaceFormView():

    model = Place
    fields = ["name", "description", "type", "address", "picture",
              "organization"]

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = super().get_form(form_class)
        form.fields['description'] = CharField(widget=MarkdownWidget())
        return form

    def get_success_url(self):
        return reverse_lazy('place_detail',
                            args=(self.object.pk, self.object.slug,))


class PlaceCreateView(PermissionRequiredMixin, PlaceFormView, CreateView):
    permission_required = 'plateformeweb.create_place'

    def validate_image(self, image):
        # Asserts image is smaller than 5MB
        if image:
            if image._size > 5 * 1024 * 1024:
                raise ValidationError("L'image est trop lourde (> 5Mo)")
            return image
        else:
            raise ValidationError("Erreur dans le téléversement du fichier")

    # set owner to current user on creation
    def form_valid(self, form):
        image = form.cleaned_data.get('picture', False)
        self.validate_image(image)
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super().form_valid(form)


class PlaceEditView(PermissionRequiredMixin, PlaceFormView, AjaxUpdateView):
    permission_required = 'plateformeweb.edit_place'
    queryset = Place.objects

    def validate_image(self, image):
        # Asserts image is smaller than 5MB
        if image:
            if image._size > 5 * 1024 * 1024:
                raise ValidationError("L'image est trop lourde (> 5Mo)")
            return image
        else:
            raise ValidationError("Erreur dans le téléversement du fichier")

    def form_valid(self, form):
        image = form.cleaned_data.get('picture', False)
        self.validate_image(image)
        return super().form_valid(form)


# --- Activity Types ---


class ActivityView(DetailView):
    model = Activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class ActivityListView(ListView):
    model = Activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["list_type"] = "activity"
        return context


# --- edit ---

class ActivityFormView():
    model = Activity
    fields = ["name", "description", "picture"]

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = super().get_form(form_class)
        form.fields['description'] = CharField(widget=MarkdownWidget())
        return form

    def get_success_url(self):
        return reverse_lazy('activity_detail',
                            args=(self.object.pk, self.object.slug,))


class ActivityCreateView(PermissionRequiredMixin, ActivityFormView, CreateView):
    permission_required = 'plateformeweb.create_activity'

        # set owner to current user on creation
    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super().form_valid(form)


class ActivityEditView(PermissionRequiredMixin, ActivityFormView, AjaxUpdateView):
    permission_required = 'plateformeweb.edit_acivity'
    queryset = Activity.objects


# --- Events ---

def cancel_reservation(request, token):
    s = URLSafeSerializer('some_secret_key', salt='cancel_reservation')
    ret = s.loads(token)
    event_id = ret['event_id']
    user_id = ret['user_id']
    event = Event.objects.get(pk=event_id)
    user = CustomUser.objects.get(pk=user_id)
    context = {'event': event, 'user': user}
    attendees = event.attendees.all()
    if user in attendees:
        event.attendees.remove(user)
        event.available_seats += 1
        event.save()
        return render(request, 'mail/cancel_ok.html', context)
    else:
        return render(request, 'mail/cancel_failed.html', context)


class EventView(DetailView):
    model = Event

    def get(self, request, **kwargs):
        event = Event.objects.get(pk=kwargs['pk'])
        confirmed = event.presents.all()
        for person in confirmed:
            event.attendees.remove(person)

        return super().get(request)



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = context['event']
        context['event_id'] = event.id
        orga = event.organization
        admins = orga.admins()
        orga_volunteers = orga.volunteers()

        volunteers = []
        for v in orga_volunteers:
            if v in event.attendees.all():
                volunteers.append(v)

        context['admin_or_volunteer'] = admins + volunteers
        context['volunteers'] = volunteers
        context['admins'] = admins
        return context


class EventListView(ListView):
    queryset = {}

    def get(self, request, **kwargs):
        return render(request, "plateformeweb/event_list.html", {})


    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)

    #     context["list_type"] = "event"
    #     return context


# --- edit ---

class EventFormView():
    model = Event
    fields = ["title", "type", "starts_at", "ends_at", "available_seats",
              "attendees", "organizers", "location", "publish_at", "published",
              "organization", "condition"]

    # date picker from
    #   https://xdsoft.net/jqplugins/datetimepicker/
    # installed as a django app by
    #   https://github.com/beda-software/django-datetimepicker
    # fix get_form:
    #   https://github.com/tomwalker/django_quiz/issues/71
    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = super().get_form(form_class)
        for field in ("starts_at", "ends_at", "publish_at"):
            form.fields[field].widget = DateTimePicker(
                options={
                    'format': '%Y-%m-%d %H:%M',
                    # todo: i18n not working yet, needs to add a static JS
                    # file for translations ?
                    # see https://xdsoft.net/jqplugins/datetimepicker/
                    'lang': self.request.LANGUAGE_CODE[:2],
                    'step': 15,
                }
            )

        form.fields["available_seats"].widget.attrs['min'] = "0"

        return form

    def get_success_url(self):
        return reverse_lazy('event_detail',
                            args=(self.object.pk, self.object.slug,))


class EventCreateView(PermissionRequiredMixin, EventFormView, CreateView):
    permission_required = 'plateformeweb.create_event'

    # set owner to current user on creation
    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user

        # if no title is specified
        if self.request.POST['title'] == '':
            new_slug = str(obj.type)
            new_slug += '-' + obj.organization.slug
            new_slug += '-' + obj.location.slug
            obj.title = obj.type
            obj.slug = new_slug

        return super().form_valid(form)





class EventEditView(PermissionRequiredMixin, EventFormView, AjaxUpdateView):
    permission_required = 'plateformeweb.edit_event'
    fields = ["title", "type", "starts_at", "ends_at", "available_seats",
              "attendees", "presents", "organizers", "location", "publish_at", "published",
              "organization", "condition"]
    queryset = Event.objects


# --- booking form for current user ---


class BookingFormView():
    model = Event
    fields = []

    def get_form(self, form_class=None, **kwargs):
        if form_class is None:
            form_class = self.get_form_class()

        user_id = self.request.user.id
        event_id = self.request.resolver_match.kwargs['pk']
        user = CustomUser.objects.get(pk=user_id)
        event = Event.objects.get(pk=event_id)
        organization = event.organization
        attendees = event.attendees.all()
        available_seats = event.available_seats
        form = super().get_form(form_class)
        print(form_class)
        print(event)
        print(attendees)

        # if form.is_valid():
        #     if user in attendees:
        #         print("if user in attendees")
        #         available_seats += 1
        #         event.attendees.remove(user)
        #     else:
        #         print("else")
        #         if event.available_seats >= 0:
        #             print("av_seats > 0")
        #             available_seats -= 1
        #             event.attendees.add(user)
        #             self.send_booking_mail(user, event)
        #         else:
        #             raise ValidationError("Trop de gens")

        #     event.available_seats = available_seats
        #     print(event.available_seats)
        #     event.save()
        return form

    def send_booking_mail(self, user, event):
        user_id = user.id
        event_id = event.id

        serial = URLSafeSerializer('some_secret_key',
                                   salt='cancel_reservation')
        data = {'event_id': event_id, 'user_id': user_id}

        cancel_token = serial.dumps(data)
        cancel_url = reverse('cancel_reservation', args=[cancel_token])
        cancel_url = self.request.build_absolute_uri(cancel_url)

        event_url = reverse('event_detail', args=[event_id, event.slug])
        event_url = self.request.build_absolute_uri(event_url)

        params = {'cancel_url': cancel_url,
                  'event_url': event_url,
                  'event': event}

        msg_plain = render_to_string('mail/relance.html',
                                    params)
        msg_html = render_to_string('mail/relance.html',
                                    params)

        date = event.starts_at.date().strftime("%d %B")
        location = event.location.name
        subject = "Votre réservation pour le " + date + " à " + location

        mail.send(
            [user.email],
            'debugsoude@gmail.com',
            subject=subject,
            message=msg_plain,
            html_message=msg_html
        )

    def get_success_url(self):
        return render(request, 'plateformeweb/event_list.html', message="c'est tout bon")


class BookingEditView(BookingFormView, AjaxUpdateView):
    template_name = 'plateformeweb/booking_form.html'
    queryset = Event.objects

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_id = context['event'].id

        serial = URLSafeSerializer('some_secret_key',
                                   salt='book')

        data = {'event_id': event_id}
        context['booking_id'] = serial.dumps(data);
        return context



# --- mass event ---

class MassEventCreateView(PermissionRequiredMixin, EventFormView, CreateView):
    permission_required = 'plateformeweb.create_event'
    template_name = 'plateformeweb/mass_event_form.html'
    model = Event
    fields = ["type",  "available_seats",
              "location", "organization",
              "starts_at", "ends_at", "publish_at"]

    def date_substract(self, starts_at, countdown):
        #TODO: change this if haing a publish_date in the past is a problem
        return starts_at - datetime.timedelta(days=countdown)


    def post(self, request, *args, **kwargs):
        try:
            import simplejson as json
        except (ImportError,):
            import json

        json_data = request.POST['dates']
        starts_at = request.POST['starts_at']
        ends_at = request.POST['ends_at']
        publish_countdown = int(request.POST['publish_at'])
        date_timestamps = json.loads(json_data)

        event_type=Activity.objects.get(pk=request.POST['type'])
        organization=Organization.objects.get(pk=request.POST['organization'])
        available_seats=int(request.POST['available_seats'])
        location=Place.objects.get(pk=request.POST['location'])

        new_slug = str(event_type)
        new_slug += '-' + organization.slug
        new_slug += '-' + location.slug

        # today = timezone.now()

        for date in date_timestamps:
            starts_at = datetime.datetime.fromtimestamp(
                int(date + int(request.POST['starts_at'])))
            ends_at = datetime.datetime.fromtimestamp(
                int(date + int(request.POST['ends_at'])))
            publish_date = self.date_substract(starts_at, publish_countdown)

            e = Event.objects.create(
                organization=organization,
                slug=new_slug,
                owner=request.user,
                starts_at=starts_at,
                ends_at=ends_at,
                publish_at=publish_date,
                available_seats=available_seats,
                location=location,
                type=event_type,
            )

            e.organizers.add(CustomUser.objects.get(email=request.user))
            e.title = e.type.name
            e.save()

        return HttpResponse("OK!")

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        form = super().get_form(form_class)
        for field in ("starts_at", "ends_at", "publish_at"):
            form.fields[field].widget = forms.HiddenInput()

        limited_choices = []
        available_organizations = OrganizationPerson.objects.filter(user=self.request.user)
        for result in available_organizations:
            if result.role >=OrganizationPerson.ADMIN:
                organization = result.organization
                limited_choices.append([organization.pk, organization.name])

        form.fields['organization'].choices = limited_choices

        return form


    # set owner to current user on creation
    def form_valid(self, form):
        return super().form_valid(form)

class MassBookingCreateView(CreateView):
    template_name = 'plateformeweb/mass_event_book.html'
    model = Event
    fields = []

    def post(self, request, *args, **kwargs):
        try:
            import simplejson as json
        except (ImportError,):
            import json

        json_data = request.POST['dates']
        events_pk = json.loads(json_data)
        events_pk = list(map(int, events_pk))
        events = Event.objects.filter(pk__in=events_pk)
        #TODO: bulk insert somehow?
        for event in events:
            event.attendees.add(request.user)

        return HttpResponse("OK!")

    def get_form(self, form_class=None, **kwargs):
        if form_class is None:
            form_class = self.get_form_class()
        form = super().get_form(form_class)

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context

    def get_success_url(self):
        return render(request, 'plateformeweb/event_list.html', message="c'est tout bon")
