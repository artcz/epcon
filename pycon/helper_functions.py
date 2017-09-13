# coding: utf-8

"""
Module temporarily created on 2017-09-12 for all the functions that used to be
defined inside settings.py
"""

from django.conf import settings


def CONFERENCE_TICKETS(conf, ticket_type=None, fare_code=None):
    from p3 import models

    tickets = models.Ticket.objects \
        .filter(fare__conference=conf, orderitem__order___complete=True)
    if ticket_type:
        tickets = tickets.filter(fare__ticket_type=ticket_type)
    if fare_code:
        if fare_code.endswith('%'):
            tickets = tickets.filter(fare__code__startswith=fare_code[:-1])
        else:
            tickets = tickets.filter(fare__code=fare_code)
    return tickets


def CONFERENCE_VOTING_OPENED(conf, user):
    # Can access the page:
    #   anyone during community voting
    #   superusers
    #   speakers (of current conference)
    #   who is in the special "pre_voting" group
    if user.is_superuser:
        return True

    # Only allow access during talk voting period
    if conf.voting():
        return True
    else:
        return False

    # XXX Disabled these special cases, since it's not clear
    #     what they are used for
    if 0:
        from p3.models import TalkSpeaker, Speaker
        try:
            count = TalkSpeaker.objects.filter(
                talk__conference=settings.CONFERENCE_CONFERENCE,
                speaker=user.speaker).count()
        except (AttributeError, Speaker.DoesNotExist):
            pass
        else:
            if count > 0:
                return True

        # Special case for "pre_voting" group members;
        if user.groups.filter(name='pre_voting').exists():
            return True

    return False


def CONFERENCE_VOTING_ALLOWED(user):

    """ Determine whether user is allowed to participate in talk voting.

    """
    if not user.is_authenticated():
        return False
    if user.is_superuser:
        return True

    # Speakers of the current conference are always allowed to vote
    from p3.models import TalkSpeaker, Speaker
    try:
        count = TalkSpeaker.objects.filter(
            talk__conference=settings.CONFERENCE_CONFERENCE,
            speaker=user.speaker).count()
    except Speaker.DoesNotExist:
        pass
    else:
        if count > 0:
            return True

    # People who have a ticket for the current conference assigned to
    # them can vote
    from p3 import models
    # Starting with EP2017, we allow people who have bought tickets in the
    # past, to also past to participate in talk voting.
    tickets = models.TicketConference.objects.filter(
        ticket__fare__conference__in=settings.CONFERENCE_TALK_VOTING_ELIGIBLE,
        assigned_to=user.email
    )

    # Starting with EP2017, we know that all assigned tickets have
    # .assigned_to set correctly
    # tickets = models.TicketConference.objects \
    #          .filter(ticket__fare__conference=CONFERENCE_CONFERENCE,
    #                  assigned_to=user.email)

    # Old query:
    # from django.db.models import Q
    # tickets = models.TicketConference.objects \
    #     .available(user, CONFERENCE_CONFERENCE) \
    #     .filter(Q(orderitem__order___complete=True) | Q(
    #     orderitem__order__method='admin')) \
    #     .filter(Q(p3_conference=None) | Q(p3_conference__assigned_to='') | Q(
    #     p3_conference__assigned_to=user.email))
    return tickets.count() > 0


def CONFERENCE_SCHEDULE_ATTENDEES(schedule, forecast):
    from p3.stats import presence_days
    from conference.models import Schedule

    if not isinstance(schedule, Schedule):
        output = {}
        for s in Schedule.objects.filter(conference=schedule):
            output[s.id] = CONFERENCE_SCHEDULE_ATTENDEES(s, forecast)
        return output
    d = schedule.date.strftime('%Y-%m-%d')
    s = presence_days(schedule.conference)
    for row in s['data']:
        if row['title'] == '%s (no staff)' % d:
            if forecast:
                return row['total_nc']
            else:
                return row['total']
    return 0

######


def CONFERENCE_VIDEO_COVER_EVENTS(conference):
    from conference import dataaccess
    from conference import models
    from datetime import timedelta

    conf = models.Conference.objects.get(code=conference)

    def valid(e):
        if e['tags'] & set(['special', 'break']):
            return False
        # sprints are in the last two days
        if e['time'].date() >= conf.conference_end - timedelta(days=1):
            return False
        # evening events are not recorded
        if e['time'].hour >= 20:
            return False
        if len(e['tracks']) == 1 and (
            e['tracks'][0] in ('helpdesk1', 'helpdesk2')
        ):
            return False
        return True

    return [x['id'] for x in filter(valid, dataaccess.events(conf=conference))]


def CONFERENCE_VIDEO_COVER_IMAGE(eid, type='front', thumb=False):
    import re
    import os.path
    from PIL import Image, ImageDraw, ImageFont
    from p3 import dataaccess

    event = dataaccess.event_data(eid)
    conference = event['conference']

    stuff = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'documents', 'cover',
                     conference))
    if not os.path.isdir(stuff):
        return None

    def wrap_text(font, text, width):
        words = re.split(' ', text)
        lines = []
        while words:
            word = words.pop(0).strip()
            if not word:
                continue
            if not lines:
                lines.append(word)
            else:
                line = lines[-1]
                w, h = font.getsize(line + ' ' + word)
                if w <= width:
                    lines[-1] += ' ' + word
                else:
                    lines.append(word)

        for ix, line in enumerate(lines):
            line = line.strip()
            while True:
                w, h = font.getsize(line)
                if w <= width:
                    break
                line = line[:-1]
            lines[ix] = line
        return lines

    if conference in ('ep2012', 'ep2013', 'ep2015', 'ep2016', 'ep2017'):
        master = Image.open(
            os.path.join(stuff, 'cover-start-end.png')
        ).convert('RGBA')

        if type == 'back':
            return master

        if conference == 'ep2012':
            ftitle = ImageFont.truetype(
                os.path.join(stuff, 'League Gothic.otf'),
                36, encoding="unic")
            fauthor = ImageFont.truetype(
                os.path.join(stuff, 'Arial_Unicode.ttf'),
                21, encoding="unic")
            y = 175
        elif conference in ('ep2013', 'ep2015', 'ep2016', 'ep2017'):
            ftitle = ImageFont.truetype(
                os.path.join(stuff, 'League_Gothic.otf'),
                36, encoding="unic")
            fauthor = ImageFont.truetype(
                os.path.join(stuff, 'League_Gothic.otf'),
                28, encoding="unic")
            y = 190

        width = master.size[0] - 40
        d = ImageDraw.Draw(master)

        title = event['name']
        if event.get('custom'):
            # this is a custom event, if starts with an anchor we can
            # extract the reference
            m = re.match(r'<a href="(.*)">(.*)</a>', title)
            if m:
                title = m.group(2)
        lines = wrap_text(ftitle, title, width)
        for l in lines:
            d.text((20, y), l, font=ftitle, fill=(0x2f, 0x1c, 0x1c, 0xff))
            y += ftitle.getsize(l)[1] + 8

        if event.get('talk'):
            spks = [x['name'] for x in event['talk']['speakers']]
            text = 'by ' + ','.join(spks)
            lines = wrap_text(fauthor, text, width)
            for l in lines:
                d.text((20, y), l, font=fauthor, fill=(0x3d, 0x7e, 0x8a, 0xff))
                y += fauthor.getsize(l)[1] + 8

        if thumb:
            master.thumbnail(thumb, Image.ANTIALIAS)
        return master
    else:
        return None

######


def CONFERENCE_TICKET_BADGE_PREPARE_FUNCTION(tickets):
    from p3.utils import conference_ticket_badge

    return conference_ticket_badge(tickets)


def CONFERENCE_TALK_VIDEO_ACCESS(request, talk):
    return True
    if talk.conference != settings.CONFERENCE_CONFERENCE:
        return True
    u = request.user
    if u.is_anonymous():
        return False
    from p3.models import Ticket

    qs = Ticket.objects \
        .filter(id__in=[x.id for x in u.assopy_user.tickets()]) \
        .filter(orderitem__order___complete=True,
                fare__ticket_type='conference')
    return qs.exists()


def ASSOPY_ORDERITEM_CAN_BE_REFUNDED(user, item):
    if user.is_superuser:
        return True
    return False
    if not item.ticket:
        return False
    ticket = item.ticket
    if ticket.user != user:
        return False
    if ticket.fare.conference != settings.CONFERENCE_CONFERENCE:
        return False
    if item.order.total() == 0:
        return False
    return item.order._complete

#######


def HCOMMENTS_RECAPTCHA(request):
    return not request.user.is_authenticated()


def HCOMMENTS_THREAD_OWNERS(o):
    from p3.models import P3Talk

    if isinstance(o, P3Talk):
        return [s.user for s in o.get_all_speakers()]
    return None


def HCOMMENTS_MODERATOR_REQUEST(request, comment):
    if request.user.is_superuser:
        return True
    else:
        owners = HCOMMENTS_THREAD_OWNERS(comment.content_object)
        if owners:
            return request.user in owners
    return False

#######


def P3_LIVE_REDIRECT_URL(request, track):
    internal = False
    for check in settings.P3_LIVE_INTERNAL_IPS:
        if request.META['REMOTE_ADDR'].startswith(check):
            internal = True
            break
    url = None
    if internal:
        import re

        ua = request.META['HTTP_USER_AGENT']

        base = '{0}/{1}'.format(
            settings.P3_INTERNAL_SERVER,
            settings.P3_LIVE_TRACKS[track]['stream']['internal']
        )
        if re.search('Android', ua, re.I):
            url = 'rtsp://' + base
        elif re.search('iPhone|iPad|iPod', ua, re.I):
            url = 'http://%s/playlist.m3u8' % base
        else:
            url = 'rtmp://' + base
    else:
        try:
            url = 'https://www.youtube.com/watch?v={0}'.format(
                settings.P3_LIVE_TRACKS[track]['stream']['external']
            )
        except KeyError:
            pass
    return url


def P3_LIVE_EMBED(request, track=None, event=None):
    from django.core.cache import cache

    if not any((track, event)) or all((track, event)):
        raise ValueError('track or event, not both')

    if event:
        # ep2012, all keynotes are recorded in track "lasagne"
        if 'keynote' in event['tags'] or len(event['tracks']) > 1:
            track = 'track2'
        else:
            track = event['tracks'][0]

    internal = False

    for check in settings.P3_LIVE_INTERNAL_IPS:
        if request.META['REMOTE_ADDR'].startswith(check):
            internal = True
            break

    if internal:
        try:
            url = '{0}/{1}'.format(
                settings.P3_INTERNAL_SERVER,
                settings.P3_LIVE_TRACKS[track]['stream']['internal']
            )
        except KeyError:
            return None
        data = {
            'track': track,
            'stream': url.rsplit('/', 1)[1],
            'url': url,
        }
        # TODO: move that to a template file
        html = ("""
        <div>
            <div class="button" style="float: left; margin-right: 20px;">
                <h5><a href="rtsp://%(url)s">RTSP</a></h5>
                For almost all<br/>Linux, Windows, Android
            </div>
            <div class="button" style="float: left; margin-right: 20px;">
                <h5><a href="http://%(url)s/playlist.m3u8">HLS&#xF8FF;</a></h5>
                Apple world (mainly)
            </div>
            <div class="button" style="float: left; margin-right: 20px;">
                <h5><a href="#" onclick="start_%(stream)s(); return false;">Flash</a></h5>
                Old good school
            </div>
            <div id="stream-%(track)s" style="clear: both();width:530px;height:298px;margin:0 auto;text-align:center"> </div>
            <script>
                function start_%(stream)s() {
                    $f("stream-%(track)s", "/static/p5/flowplayer/flowplayer-3.2.12.swf", {

                        clip: {
                            autoPlay: false,
                            url: 'mp4:%(stream)s',
                            scaling: 'fit',
                            // configure clip to use hddn as our provider, refering to our rtmp plugin
                            provider: 'hddn'
                        },

                        // streaming plugins are configured under the plugins node
                        plugins: {

                            // here is our rtmp plugin configuration
                            hddn: {
                                url: "/static/p5/flowplayer/flowplayer.rtmp-3.2.10.swf",

                                // netConnectionUrl defines where the streams are found
                                netConnectionUrl: 'rtmp://%(url)s'
                            }
                        }
                    });
                }
            </script>
        </div>
        """ % data)  # " (makes emacs highlighting happy)
        return html
    else:
        data = cache.get('p3_live_embed_%s' % track)
        if data is not None:
            return data

        try:
            yurl = 'https://www.youtube.com/watch?v={0}'.format(
                settings.P3_LIVE_TRACKS[track]['stream']['external']
            )
        except KeyError:
            return None

        import httplib2
        import json

        http = httplib2.Http()
        service = 'https://www.youtube.com/oembed'
        url = service + '?url=' + yurl + '&format=json&scheme=https'
        try:
            response, content = http.request(url)
            data = json.loads(content)
        except:
            return None
        cache.set('p3_live_embed_%s' % track, data['html'], 3600)
        return data['html']


# cronjob
def cron_cleanup():
    from django.core.management.commands import cleanup

    cmd = cleanup.Command()
    cmd.handle()
