import datetime
import re

from flask import current_app
from namex.models import User, State, Comment, PartnerNameSystem, Name, Applicant

from namex.services.nro.utils import ora_row_to_dict


def add_nr_header(nr, nr_header, nr_submitter, user):

    NR_STATE={
        'HISTORICAL': 'HISTORICAL',
        'H': 'HOLD',
        'COMPLETED': 'COMPLETED',
        'D': 'DRAFT',
        'C': 'CANCELLED',
        'E': 'EXPIRED'
    }

    if nr_submitter:
        submitter = User.find_by_username(nr_submitter['submitter'])
    else:
        submitter = None

    previous_priorityCd = nr.priorityCd

    nr.userId = user.id
    nr.stateCd = State.DRAFT if nr_header['state_type_cd'] is None else NR_STATE[nr_header['state_type_cd']]
    nr.nrNum = nr_header['nr_num']
    nr.requestId = nr_header['request_id']
    nr.previousRequestId = nr_header['previous_request_id']
    nr.submitCount = nr_header['submit_count']
    nr.requestTypeCd = nr_header['request_type_cd']
    nr.expirationDate = nr_header['expiration_date']
    nr.additionalInfo = nr_header['additional_info']
    nr.natureBusinessInfo = nr_header['nature_business_info']
    nr.xproJurisdiction = nr_header['xpro_jurisdiction']
    # TODO This should NOT be None, but due to some legacy issues, it's set to None
    nr.submittedDate = None if not nr_submitter else nr_submitter['submitted_date']
    nr.submitter_userid = None if not submitter else submitter.id
    nr.nroLastUpdate = nr_header['last_update']
    nr.lastUpdate = nr.nroLastUpdate # this needs to be set to the same Point In Time as NRO until NameX owns it

    if nr_header['priority_cd'] == 'PQ':
        nr.priorityCd = 'Y'
        if previous_priorityCd == 'N':
            nr.priorityDate = datetime.datetime.utcnow()
        else:
            nr.priorityDate = nr.submittedDate
    else:
        nr.priorityCd = 'N'

    # if this was a change of name with related corp num, populate the corpNum field
    # - the string in Additional Info field is form: **Change of Name** **XXXXXXXXXXXXXX**
    try:
        if '**Change of Name**' in nr.additionalInfo:
            regex = r"\*\*Change of Name\*\* \*\*([a-zA-Z0-9]*)\*\*"
            m = re.search(regex, nr.additionalInfo)
            if m:
                nr.corpNum = m.group(1)
    except:
        pass


def add_comments(nr, comments):
    # TODO: link to examiner IDs somehow - examiner_IDIR
    # TODO: append new comments, rather than flushing out all the old ones first
    for com in nr.comments.all():
        nr.comments.remove(com)

    if comments:
        for c in comments:
            comm = Comment()
            comm.comment = c['examiner_comment']
            comm.timestamp = c['event_timestamp']

            nr.comments.append(comm)


def add_nwpta(nr, nr_nwpta):

    # naive approach, if updating remove all the old PNS'es
    # TODO change to an update / delete / insert flow
    for pn in nr.partnerNS.all():
        nr.partnerNS.remove(pn)

    if nr_nwpta:
        for p in nr_nwpta:
            pns = PartnerNameSystem()
            pns.partnerNameTypeCd = p['partner_name_type_cd']
            pns.partnerNameNumber = p['partner_name_number']
            pns.partnerJurisdictionTypeCd = p['partner_jurisdiction_type_cd']
            pns.partnerNameDate = p['partner_name_date']
            pns.partnerName = p['partner_name']

            pns.set_requested_flag()

            nr.partnerNS.append(pns)


def add_names(nr, nr_names):
    NAME_STATE={
        'NE': Name.NOT_EXAMINED,
        'A': Name.APPROVED,
        'R': Name.REJECTED,
        'C': Name.CONDITION
    }
    # naive approach
    # TODO change to an update / delete / insert flow
    # remove all names
    for ne in nr.names.all():
        nr.names.remove(ne)

    # add in the names from this request
    for n in nr_names:
        name = Name()
        name.state = Name.NOT_EXAMINED if n['name_state_type_cd'] is None else NAME_STATE[n['name_state_type_cd']]
        name.choice = n['choice_number']
        name.name = n['name']
        name.designation = n['designation']

        if nr.stateCd in ['COMPLETED', State.REJECTED] and name.state == Name.APPROVED:
            nr.stateCd = State.APPROVED
        elif nr.stateCd in ['COMPLETED', State.REJECTED, State.APPROVED] and name.state == Name.CONDITION:
            nr.stateCd = State.CONDITIONAL
        elif nr.stateCd == 'COMPLETED' and name.state == Name.REJECTED:
            nr.stateCd = State.REJECTED

        nr.names.append(name)


def add_applicant(nr, nr_applicant):

    applicant = nr.applicants.one_or_none()

    if not applicant:
        applicant = Applicant()
        nr.applicants.append(applicant)

    applicant.lastName = nr_applicant['last_name']
    applicant.firstName = nr_applicant['first_name']
    applicant.middleName = nr_applicant['middle_name']
    applicant.phoneNumber = nr_applicant['phone_number']
    applicant.faxNumber = nr_applicant['fax_number']
    applicant.emailAddress = nr_applicant['email_address']
    applicant.contact = nr_applicant['contact']
    applicant.clientFirstName = nr_applicant['client_first_name']
    applicant.clientLastName = nr_applicant['client_last_name']
    applicant.declineNotificationInd = nr_applicant['decline_notification_ind']
    applicant.addrLine1 = nr_applicant['addr_line_1']
    applicant.addrLine2 = nr_applicant['addr_line_2']
    applicant.addrLine3 = nr_applicant['addr_line_3']
    applicant.city = nr_applicant['city']
    applicant.postalCd = nr_applicant['postal_cd']
    applicant.stateProvinceCd = nr_applicant['state_province_cd']
    applicant.countryTypeCd = nr_applicant['country_type_cd']


def get_nr_header(session, nr_num):
    # get the NR Header
    #############################
    sql_nr = (
        'select  request_id,'
        'nr_num,'
        'previous_request_id,'
        'submit_count,'
        'priority_cd,'
        'request_type_cd,'
        'expiration_date,'
        'additional_info,'
        'nature_business_info,'
        'xpro_jurisdiction'
        ' from request_vw'
        ' where nr_num = :nr'
    )
    sql_lu = (
        'select last_update'
        ' from req_instance_max_event'
        ' where request_id = :id'
    )
    sql_state = (
        'select rs.state_type_cd'
        ' from request_state_vw rs'
        ' where rs.request_id = :req_id'
        ' and rs.end_event_id IS NULL'
    )
    result = session.execute(sql_nr, nr=nr_num)
    row = result.fetchone()
    col_names = [row[0] for row in session.description]

    #get main row
    if row:
        nr = ora_row_to_dict(col_names, row)

        # get last_updated
        result = session.execute(sql_lu, id=nr['request_id'])
        row = result.fetchone()
        if row:
            col_names = [row[0] for row in session.description]
            nr = {**nr, **(ora_row_to_dict(col_names, row))}

        # get state
        result = session.execute(sql_state, req_id=nr['request_id'])
        row = result.fetchone()
        if row:
            col_names = [row[0] for row in session.description]
            nr = {**nr, **(ora_row_to_dict(col_names, row))}

            current_app.logger.debug(nr)

        return nr

    return None


def get_nr_submitter(session, request_id):

    # get the NR Submitter
    #############################
    sql = (
        'select submitted_date,'
        ' submitter'
        ' from submitter_vw'
        ' where request_id = :req_id'
    )
    result = session.execute(sql, req_id=request_id)
    row = result.fetchone()
    if row:
        col_names = [row[0] for row in session.description]
        return ora_row_to_dict(col_names, row)
    return None


def get_nr_requester(session, request_id):

    # get the NR Requester
    #############################
    sql = (
        'select  request_id,'
        ' last_name,'
        ' first_name,'
        ' middle_name,'
        ' phone_number,'
        ' fax_number,'
        ' email_address,'
        ' contact,'
        ' client_first_name,'
        ' client_last_name,'
        ' decline_notification_ind,'
        ' addr_line_1,'
        ' addr_line_2,'
        ' addr_line_3,'
        ' city,'
        ' postal_cd,'
        ' state_province_cd,'
        ' country_type_cd'
        ' from request_party_vw'
        ' where request_id = :req_id'
    )
    result = session.execute(sql, req_id=request_id)
    row = result.fetchone()
    if row:
        col_names = [row[0] for row in session.description]
        return ora_row_to_dict(col_names, row)
    return None


def get_exam_comments(session, request_id):
    # get the NR Requester
    #############################
    sql = (
        'select examiner_IDIR,'
        ' examiner_comment,'
        ' state_comment,'
        ' event_timestamp'
        ' from examiner_comments_vw'
        ' where request_id= :req_id'
    )
    result = session.execute(sql, req_id=request_id)
    col_names = [row[0] for row in session.description]
    ex_comments = []
    for row in result:
        if row[1] or row[2]:
            ex_comments.append(ora_row_to_dict(col_names, row))
    if len(ex_comments) < 1:
        return None
    return ex_comments


def get_nwpta(session, request_id):
    # get the NR NWPTA Partner information
    #############################
    sql = 'select partner_name_type_cd,' \
          ' partner_name_number,' \
          ' partner_jurisdiction_type_cd,' \
          ' partner_name_date,' \
          ' partner_name,' \
          ' last_update_id' \
          ' from partner_name_system_vw pns' \
          ' where end_event_id IS NULL' \
          ' and pns.request_id= :req_id'

    result = session.execute(sql, req_id=request_id)
    col_names = [row[0] for row in session.description]
    nwpta = []
    for row in result:
        nwpta.append(ora_row_to_dict(col_names, row))
    if len(nwpta) < 1:
        return None
    return nwpta


def get_names(session, request_id):
    # get the NRO Names
    #############################
    sql = 'select choice_number,' \
          ' name,' \
          ' designation,' \
          ' name_state_type_cd' \
          ' from names_vw' \
          ' where request_id = :req_id'
    result = session.execute(sql, req_id=request_id)
    col_names = [row[0] for row in session.description]
    names = []
    for row in result:
        names.append(ora_row_to_dict(col_names, row))
    if len(names) < 1:
        return None
    return names