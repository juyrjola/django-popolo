from django.core.validators import RegexValidator
from django.db import models
from model_utils import Choices
from model_utils.managers import PassThroughManager
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .behaviors.models import Permalinkable, Timestampable, Dateframeable
from .querysets import PostQuerySet, OtherNameQuerySet, ContactDetailQuerySet, MembershipQuerySet, OrganizationQuerySet, PersonQuerySet

class PopoloModel(models.Model):
    class Meta:
        abstract = True

if not hasattr(settings, 'POPOLO_APP_NAME'):
    raise ImproperlyConfigured("You must configure POPOLO_APP_NAME in your settings to point to your Popolo application")

model_path = lambda model_name: settings.POPOLO_APP_NAME + '.' + model_name

class ContactDetailBase(Timestampable, Dateframeable, models.Model):
    """
    A means of contacting an entity
    """

    CONTACT_TYPES = Choices(
        ('FAX', 'fax', _('Fax')),
        ('PHONE', 'phone', _('Telephone')),
        ('MOBILE', 'mobile', _('Mobile')),
        ('EMAIL', 'email', _('Email')),
        ('MAIL', 'mail', _('Snail mail')),
        ('TWITTER', 'twitter', _('Twitter')),
        ('FACEBOOK', 'facebook', _('Facebook')),
    )

    label = models.CharField(_("label"), max_length=128, blank=True, null=True, help_text=_("A human-readable label for the contact detail"))
    contact_type = models.CharField(_("type"), max_length=12, choices=CONTACT_TYPES, help_text=_("A type of medium, e.g. 'fax' or 'email'"))
    value = models.CharField(_("value"), max_length=128, help_text=_("A value, e.g. a phone number or email address"))
    note = models.CharField(_("note"), max_length=128, blank=True, null=True, help_text=_("A note, e.g. for grouping contact details by physical location"))

    objects = PassThroughManager.for_queryset_class(ContactDetailQuerySet)()

    class Meta:
        abstract = True


class IdentifierBase(models.Model):
    """
    An issued identifier
    """

    identifier = models.CharField(_("identifier"), max_length=128, help_text=_("An issued identifier, e.g. a DUNS number"))
    scheme = models.CharField(_("scheme"), max_length=128, blank=True, null=True, help_text=_("An identifier scheme, e.g. DUNS"))

    class Meta:
        abstract = True


class LinkBase(models.Model):
    """
    A URL
    """
    url = models.URLField(_("url"), help_text=_("A URL"))
    note = models.CharField(_("note"), max_length=128, blank=True, null=True, help_text=_("A note, e.g. 'Wikipedia page'"))

    class Meta:
        abstract = True


class OtherNameBase(Dateframeable, models.Model):
    """
    An alternate or former name
    """
    name = models.CharField(_("name"), max_length=128, help_text=_("An alternate or former name"))
    note = models.CharField(_("note"), max_length=256, null=True, blank=True, help_text=_("A note, e.g. 'Birth name'"))

    objects = PassThroughManager.for_queryset_class(OtherNameQuerySet)()

    class Meta:
        abstract = True

    def __unicode__(self):
        return self.name


def _generate_common_tables(model, extra_info):
    base_name = model.__name__    # e.g. 'Person'
    link_name = base_name.lower() # 'person'

    linked_info_types = [
        {
            'name': 'ContactDetail',
            'related_name': 'contact_details',
            'base_class': ContactDetailBase
        }, {
            'name': 'Link',
            'related_name': 'links',
            'base_class': LinkBase
        }, {
            'name': 'Source',
            'related_name': 'sources',
            'base_class': LinkBase
        },
    ]
    if extra_info:
        linked_info_types +=  [
            {
                'name': 'Identifier',
                'related_name': 'identifiers',
                'base_class': IdentifierBase
            }, {
                'name': 'OtherName',
                'related_name': 'other_names',
                'base_class': OtherNameBase
            }
        ]

    for info in linked_info_types:
        class Meta:
            abstract = True

        class_name = base_name + info['name'] # PersonContactDetail
        linked_info_model = type(class_name, (PopoloModel, info['base_class']), {
            # Django requires __module__ as a model attribute
            '__module__': __name__,
            'Meta': Meta,
            link_name: models.ForeignKey(model_path(base_name),
                                         related_name=info['related_name']),
        })
        globals()[class_name] = linked_info_model


class Person(Dateframeable, Timestampable, Permalinkable, PopoloModel):
    """
    A real person, alive or dead
    """
    GENDERS = Choices(
        (0, 'female', _('Female')),
        (1, 'male', _('Male')),
    )

    name = models.CharField(_("name"), max_length=128, help_text=_("A person's preferred full name"))
    family_name = models.CharField(_("family name"), max_length=128, null=True, blank=True, help_text=_("One or more family names"))
    given_name = models.CharField(_("given name"), max_length=128, null=True, blank=True, help_text=_("One or more primary given names"))
    additional_name = models.CharField(_("additional name"), max_length=128, null=True, blank=True, help_text=_("One or more secondary given names"))
    honorific_prefix = models.CharField(_("honorific prefix"), max_length=128, null=True, blank=True, help_text=_("One or more honorifics preceding a person's name"))
    honorific_suffix = models.CharField(_("honorific suffix"), max_length=128, null=True, blank=True, help_text=_("One or more honorifics following a person's name"))
    patronymic_name = models.CharField(_("patronymic name"), max_length=128, null=True, blank=True, help_text=_("One or more patronymic names"))
    sort_name = models.CharField(_("sort name"), max_length=128, null=True, blank=True, help_text=_("A name to use in an lexicographically ordered list"))
    email = models.EmailField(_("email"), blank=True, null=True, help_text=_("A preferred email address"))
    gender = models.IntegerField(_('gender'), choices=GENDERS, null=True, blank=True, help_text=_("A gender"))
    birth_date = models.CharField(_("birth date"), max_length=10, null=True, blank=True, help_text=_("A date of birth"))
    death_date = models.CharField(_("death date"), max_length=10, null=True,blank=True, help_text=_("A date of death"))
    summary = models.CharField(_("summary"), max_length=512, null=True, blank=True, help_text=_("A one-line account of a person's life"))
    biography = models.TextField(_("biography"), null=True, blank=True, help_text=_("An extended account of a person's life"))
    image = models.URLField(_("image"), blank=True, null=True, help_text=_("A URL of a head shot"))

    # array of items referencing "http://popoloproject.com/schemas/membership.json#"
    @property
    def memberships(self):
        return self.membership_set.all()

    @property
    def slug_source(self):
        return self.name

    url_name = 'person-detail'
    objects = PassThroughManager.for_queryset_class(PersonQuerySet)()

    class Meta:
        abstract = True

_generate_common_tables(Person, True)


class Organization(Dateframeable, Timestampable, Permalinkable, PopoloModel):
    """
    A group with a common purpose or reason for existence that goes beyond the set of people belonging to it
    """

    name = models.CharField(_("name"), max_length=128, help_text=_("A primary name, e.g. a legally recognized name"))
    classification = models.CharField(_("classification"), max_length=128, null=True, blank=True, help_text=_("An organization category, e.g. committee"))
    # reference to "http://popoloproject.com/schemas/organization.json#"
    parent = models.ForeignKey(model_path('Organization'), null=True, help_text=_("The ID of the organization that contains this organization"))

    dissolution_date = models.CharField(_("dissolution date"), max_length=10, blank=True, null=True, validators=[
                    RegexValidator(
                        regex='^[0-9]{4}(-[0-9]{2}){0,2}$',
                        message='dissolution date must follow the given pattern: ^[0-9]{4}(-[0-9]{2}){0,2}$',
                        code='invalid_dissolution_date'
                    )
                ], help_text=_("A date of dissolution"))
    founding_date = models.CharField(_("founding date"), max_length=10, blank=True, null=True, validators=[
                    RegexValidator(
                        regex='^[0-9]{4}(-[0-9]{2}){0,2}$',
                        message='founding date must follow the given pattern: ^[0-9]{4}(-[0-9]{2}){0,2}$',
                        code='invalid_founding_date'
                    )
                ], help_text=_("A date of founding"))


    @property
    def slug_source(self):
        return self.name

    url_name = 'organization-detail'
    objects = PassThroughManager.for_queryset_class(OrganizationQuerySet)()

    class Meta:
        abstract = True

_generate_common_tables(Organization, True)


class Post(Dateframeable, Timestampable, Permalinkable, PopoloModel):
    """
    A position that exists independent of the person holding it
    """

    label = models.CharField(_("label"), max_length=128, help_text=_("A label describing the post"))
    role = models.CharField(_("role"), max_length=128, null=True, blank=True, help_text=_("The function that the holder of the post fulfills"))

    # reference to "http://popoloproject.com/schemas/organization.json#"
    organization = models.ForeignKey(model_path('Organization'), related_name='posts',
                                     help_text=_("The organization in which the post is held"))

    @property
    def slug_source(self):
        return self.label

    objects = PassThroughManager.for_queryset_class(PostQuerySet)()

    class Meta:
        abstract = True

_generate_common_tables(Post, False)


class Membership(Dateframeable, Timestampable, PopoloModel):
    """
    A relationship between a person and an organization
    """

    label = models.CharField(_("label"), max_length=128, null=True, blank=True, help_text=_("A label describing the membership"))
    role = models.CharField(_("role"), max_length=128, null=True, blank=True, help_text=_("The role that the person fulfills in the organization"))

    # reference to "http://popoloproject.com/schemas/person.json#"
    person = models.ForeignKey(model_path('Person'), related_name='memberships',
                               help_text=_("The person who is a party to the relationship"))

    # reference to "http://popoloproject.com/schemas/organization.json#"
    organization = models.ForeignKey(model_path('Organization'), related_name='memberships',
                                     help_text=_("The organization that is a party to the relationship"))
    on_behalf_of = models.ForeignKey(model_path('Organization'), related_name='memberships_on_behalf_of',
                                     help_text=_("The organization on whose behalf the person is a party to the relationship"))

    # reference to "http://popoloproject.com/schemas/post.json#"
    post = models.ForeignKey(model_path('Post'), null=True, related_name='memberships',
                             help_text=_("The post held by the person in the organization through this membership"))

    @property
    def slug_source(self):
        return self.label

    objects = PassThroughManager.for_queryset_class(MembershipQuerySet)()

    class Meta:
        abstract = True

_generate_common_tables(Membership, False)

##
## signals
##

## all instances are validated before being saved
@receiver(pre_save, sender=Person)
@receiver(pre_save, sender=Organization)
@receiver(pre_save, sender=Post)
def validate_date_fields(sender, **kwargs):
    obj = kwargs['instance']
    obj.full_clean()
