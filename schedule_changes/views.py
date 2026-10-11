import re
from datetime import datetime
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import TravelAgency, ProcessedBooking, UserProfile

AIRPORT_CODES = {
    'LUN': 'Lusaka', 'LVI': 'Livingstone', 'NLA': 'Ndola',
    'MFU': 'Mfuwe', 'SMQ': 'Solwezi', 'MNX': 'Mansa', 'KLB': 'Kalabo',
    'JNB': 'Johannesburg', 'CPT': 'Cape Town', 'DUR': 'Durban',
    'WDH': 'Windhoek', 'DAR': 'Dar es Salaam', 'GBE': 'Gaborone',
    'KAA': 'Kasama', 'SLI': 'Solwezi'
}

def format_time(time_str):
    try: return datetime.strptime(time_str, "%H%M").strftime("%I:%M %p").lstrip("0")
    except: return time_str

def format_date(date_str):
    try:
        d_str = date_str if len(date_str) == 7 else f"{date_str}{datetime.now().strftime('%y')}"
        d = datetime.strptime(d_str, '%d%b%y')
        suffix = 'th' if 11 <= d.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')
        return d.strftime(f"%A, %B {d.day}{suffix}")
    except: return date_str

def clean_agency_name(name):
    if not name: return ""
    cleaned = re.sub(r'Travel\s*Part|ner|Travel\s*Partner', '', name, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else name.strip()

def login_view(request):
    if request.method == "POST":
        action = request.POST.get('action')
        vars_input = request.POST.get('vars_username')
        
        if not vars_input:
            return render(request, 'login.html', {'error': 'Please enter your VARS Username.'})
            
        vars_username = vars_input.strip().upper()
        password = request.POST.get('password')

        if action == 'signup':
            real_name = request.POST.get('real_name')
            if not real_name:
                return render(request, 'login.html', {'error': 'Please enter your Real Full Name.'})
                
            if not User.objects.filter(username=vars_username).exists():
                user = User.objects.create_user(username=vars_username, password=password)
                UserProfile.objects.create(user=user, vars_username=vars_username, real_name=real_name)
                login(request, user)
                return redirect('process_pnr')
            else:
                return render(request, 'login.html', {'error': 'VARS Username already exists.'})
        else:
            user = authenticate(request, username=vars_username, password=password)
            if user is not None:
                login(request, user)
                return redirect('process_pnr')
            else:
                return render(request, 'login.html', {'error': 'Invalid VARS Username or Password.'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login_view')

@login_required(login_url='login_view')
def process_pnr(request):
    try:
        agent_name = request.user.userprofile.real_name
    except UserProfile.DoesNotExist:
        agent_name = request.user.username

    if not TravelAgency.objects.exists():
        initial_agencies = [
            {'iata': '67200070', 'name': 'Blueberry Travel Limited', 'email': 'info@blueberrytravel.co.zm', 'phone': '+260978443322'},
            {'iata': '77266055', 'name': 'Teichmann Plant Hire', 'email': 'travel@teichmanngrp.com', 'phone': '+27315693170'},
            {'iata': '77206673', 'name': 'Travel Partner JNB', 'email': 'reservations@travelpartner.co.za', 'phone': '+27118225516'},
            {'iata': '67210360', 'name': 'Eagle Travel', 'email': 'info@eagletravel.co.zm', 'phone': '+260212226806'},
            {'iata': '67210253', 'name': 'Travel Partner LUN', 'email': 'info@travelpartner.co.zm', 'phone': '+260211252525'},
            {'iata': '67200630', 'name': 'Voyagers Zambia', 'email': 'tours@voyagerszambia.com', 'phone': '+260212622000'}, 
            {'iata': '67200101', 'name': 'Mukwa Travel', 'email': 'info@mukwatravel.co.zm', 'phone': '+260211252252'},
        ]
        for ag in initial_agencies:
            TravelAgency.objects.create(iata_number=ag['iata'], name=ag['name'], email=ag['email'], phone=ag['phone'])

    # CHROME-STYLE CATEGORIZED HISTORY FOR CURRENT LOGGED-IN AGENT ONLY
    now = timezone.now()
    user_bookings = ProcessedBooking.objects.filter(user=request.user).order_by('-updated_at')
    
    history_groups = {
        'Just now (< 1 min)': [],
        'Past 7 minutes': [],
        'Past 30 minutes': [],
        'Past 1 hour': [],
        'Past 3 hours': [],
        'Today': [],
        'Older': []
    }

    for b in user_bookings:
        diff_seconds = (now - b.updated_at).total_seconds()
        if diff_seconds < 60:
            history_groups['Just now (< 1 min)'].append(b)
        elif diff_seconds < 420:
            history_groups['Past 7 minutes'].append(b)
        elif diff_seconds < 1800:
            history_groups['Past 30 minutes'].append(b)
        elif diff_seconds < 3600:
            history_groups['Past 1 hour'].append(b)
        elif diff_seconds < 10800:
            history_groups['Past 3 hours'].append(b)
        elif b.updated_at.date() == now.date():
            history_groups['Today'].append(b)
        else:
            history_groups['Older'].append(b)

    categorized_history = {k: v for k, v in history_groups.items() if v}

    if request.method == "POST":
        if 'save_agency' in request.POST:
            raw_emails = ", ".join([e for e in request.POST.getlist('new_email') if e.strip()])
            raw_phones = ", ".join([p for p in request.POST.getlist('new_phone') if p.strip()])
            
            clean_emails = ", ".join(sorted(list(set([e.strip() for e in raw_emails.split(',') if e.strip()]))))
            clean_phones = ", ".join(sorted(list(set([p.strip() for p in raw_phones.split(',') if p.strip()]))))

            submitted_name = clean_agency_name(request.POST.get('new_name', ''))

            TravelAgency.objects.update_or_create(
                iata_number=request.POST.get('new_iata'),
                defaults={
                    'name': submitted_name if submitted_name else "Travel Partner", 
                    'email': clean_emails,
                    'phone': clean_phones
                }
            )
        
        raw_input = request.POST.get('pnr_text', '').strip().upper()
        
        if len(raw_input) == 6 and raw_input.isalnum():
            try:
                quick_booking = ProcessedBooking.objects.get(pnr=raw_input, user=request.user)
                return render(request, 'dashboard.html', {'quick_booking': quick_booking, 'raw_input': '', 'categorized_history': categorized_history})
            except ProcessedBooking.DoesNotExist:
                return render(request, 'dashboard.html', {'error': f"Booking {raw_input} not found in your history.", 'raw_input': '', 'categorized_history': categorized_history})

        elif raw_input.isdigit() and 7 <= len(raw_input) <= 9:
            try:
                agency_to_edit = TravelAgency.objects.get(iata_number=raw_input)
                agency_to_edit.name = clean_agency_name(agency_to_edit.name)
                return render(request, 'dashboard.html', {'agency_to_edit': agency_to_edit, 'raw_input': '', 'categorized_history': categorized_history})
            except TravelAgency.DoesNotExist:
                return render(request, 'dashboard.html', {'error': f"IATA {raw_input} not in database.", 'raw_input': '', 'categorized_history': categorized_history})

        pnr_blocks = re.split(r'(?=\s*1\.1[A-Z]+/)|-{3,}', raw_input)
        grouped_emails = {}
        missing_agencies = [] 
        
        for raw_pnr in pnr_blocks:
            if not raw_pnr.strip(): continue
                
            raw_names = re.findall(r'\d\.\d([A-Z]+)/([A-Z]+)', raw_pnr)
            processed_names = []
            for last, first in raw_names:
                p_title = ""
                for t_key, t_val in {'MRS': 'Mrs.', 'MISS': 'Ms.', 'MR': 'Mr.', 'MSTR': 'Master', 'CHD': 'Child'}.items():
                    if first.endswith(t_key):
                        first = first[:-len(t_key)]
                        p_title = t_val + " "
                        break
                processed_names.append(f"{p_title}{first.title()} {last.title()}")
            passenger_names = ", ".join(processed_names) if processed_names else "[Passenger Names]"
            
            gds_match = re.search(r'\[[A-Z0-9]{2}/([A-Z0-9]{6})\]', raw_pnr)
            gds_ref = gds_match.group(1) if gds_match else ""

            pnr_matches = re.findall(r'\b[A-Z0-9]{6}\b', raw_pnr)
            if gds_ref in pnr_matches: pnr_matches.remove(gds_ref)
            pnr = pnr_matches[-1] if pnr_matches else "[PNR]"
            
            iata_match = re.search(r'IATA NO:\s*(\d+)', raw_pnr)
            iata_no = iata_match.group(1) if iata_match else ""
            
            email_matches = re.findall(r'CTCE(?:-\d)?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})', raw_pnr)
            email = ", ".join(list(set([e.lower() for e in email_matches]))) if email_matches else ""
            
            phone_matches = re.findall(r'CTC[MH](?:-\d)?\s*([+0-9\-\s]+)', raw_pnr)
            phone_number = ", ".join(list(set([p.strip() for p in phone_matches]))) if phone_matches else ""
            
            agency_match = re.search(r'CTCT\s+(?:[A-Z]{3}\s+)?(?:\+?\d+[\s\-]*)?([A-Z\s]{3,})', raw_pnr)
            parsed_agency_name = ""
            if agency_match:
                candidate = agency_match.group(1).strip().title()
                parsed_agency_name = clean_agency_name(candidate)

            is_agency = "CTCT" in raw_pnr or "AERTICKET" in raw_pnr or "TRAVEL" in raw_pnr or bool(iata_no)
            agency_name = parsed_agency_name if parsed_agency_name else ""
            
            if is_agency and iata_no:
                try:
                    agency_record = TravelAgency.objects.get(iata_number=iata_no)
                    db_name = clean_agency_name(agency_record.name)
                    if db_name != agency_record.name:
                        agency_record.name = db_name
                        agency_record.save()

                    if agency_record.email:
                        combined_emails = f"{agency_record.email}, {email}"
                        email = ", ".join(sorted(list(set([e.strip() for e in combined_emails.split(',') if e.strip()]))))
                    if agency_record.phone: 
                        combined_phones = f"{agency_record.phone}, {phone_number}"
                        phone_number = ", ".join(sorted(list(set([p.strip() for p in combined_phones.split(',') if p.strip()]))))
                    
                    agency_name = agency_record.name if agency_record.name else agency_name
                except TravelAgency.DoesNotExist:
                    if iata_no not in [a['iata'] for a in missing_agencies]:
                        missing_agencies.append({'iata': iata_no, 'name': parsed_agency_name})
            
            final_agency_display = agency_name if agency_name else "Travel Partner"
            group_key = iata_no if (is_agency and iata_no) else (email if email else pnr)
            
            asc_lines = re.findall(r'ASC.*', raw_pnr)
            affected_dates = set([d[:5] for line in asc_lines for d in re.findall(r'(\d{2}[A-Z]{3})', line)])
            
            segments = re.findall(r'(\d+)\s+([A-Z0-9]{2})\s+(\d{3,4})\s+[A-Z]\s+[A-Z]{2}\s+(\d{2}[A-Z]{3}\d{0,2})\s*([A-Z]{3})\s*([A-Z]{3}).*?(\d{4})\s+(\d{4})', raw_pnr)
            
            formatted_flights = ""
            affected_segment_lines = set()
            local_warnings = []
            
            p0_segments = [s for s in segments if s[1] == 'P0']
            
            if not p0_segments:
                local_warnings.append(f"Booking {pnr}: No active Proflight segments found.")
                formatted_flights = "⚠️ ACTION REQUIRED: Your flights are no longer active."
            else:
                for line_num, cxr, flt, date, orig, dest, dep, arr in p0_segments:
                    if not affected_dates or date[:5] in affected_dates:
                        affected_segment_lines.add(line_num)
                        formatted_flights += f"Flight P0 {flt}: Depart {AIRPORT_CODES.get(orig, orig)} ({orig}) at {format_time(dep)} – Arrive {AIRPORT_CODES.get(dest, dest)} ({dest}) at {format_time(arr)} ({format_date(date)})\n"
                
                if not formatted_flights:
                    for line_num, cxr, flt, date, orig, dest, dep, arr in p0_segments:
                        affected_segment_lines.add(line_num)
                        formatted_flights += f"Flight P0 {flt}: Depart {AIRPORT_CODES.get(orig, orig)} ({orig}) at {format_time(dep)} – Arrive {AIRPORT_CODES.get(dest, dest)} ({dest}) at {format_time(arr)} ({format_date(date)})\n"

            tkne_matches = re.findall(r'AFX(\d+)-\d+\s+TKNE\s+(\d{3}\s?\d{10})', raw_pnr)
            affected_tickets = set()
            if tkne_matches and affected_segment_lines:
                for seg_num, tkt in tkne_matches:
                    if seg_num in affected_segment_lines: affected_tickets.add(f"{tkt.replace(' ', '')[:3]} {tkt.replace(' ', '')[3:]}")
            else:
                for t in re.findall(r'TICKET ISSUED (\d{3}\s?\d{10})(?:/\d{2})?\s+E[A-Z]{3}', raw_pnr):
                    affected_tickets.add(f"{t.replace(' ', '')[:3]} {t.replace(' ', '')[3:]}")
                    
            tickets = ", ".join(sorted(list(affected_tickets))) if affected_tickets else "[Ticket Number]"
            
            contact = final_agency_display if is_agency else passenger_names
            ProcessedBooking.objects.update_or_create(
                pnr=pnr,
                defaults={
                    'user': request.user,
                    'contact_name': contact,
                    'phone': phone_number if phone_number else "No Phone Listed",
                    'passengers': passenger_names,
                    'flights_summary': formatted_flights.strip(),
                    'raw_gds': raw_pnr
                }
            )
            
            if group_key not in grouped_emails:
                grouped_emails[group_key] = {
                    'email': email, 'phone': phone_number, 'is_agency': is_agency, 
                    'agency_name': final_agency_display, 'iata_no': iata_no, 
                    'bookings': [], 'warnings': []
                }
                
            grouped_emails[group_key]['bookings'].append({
                'pnr': pnr, 'gds_ref': gds_ref, 'passengers': passenger_names, 'tickets': tickets, 'flights': formatted_flights.strip()
            })
            if local_warnings: grouped_emails[group_key]['warnings'].extend(local_warnings)

        final_results = []
        for key, data in grouped_emails.items():
            consolidated_flights = {}
            for b in data['bookings']:
                f_key = b['flights']
                if f_key not in consolidated_flights:
                    consolidated_flights[f_key] = {'pnrs': [], 'passengers': [], 'tickets': []}
                
                p_display = f"{b['pnr']} (GDS Ref: {b['gds_ref']})" if b['gds_ref'] else b['pnr']
                consolidated_flights[f_key]['pnrs'].append(p_display)
                
                if b['passengers'] != "[Passenger Names]":
                    consolidated_flights[f_key]['passengers'].extend([p.strip() for p in b['passengers'].split(',')])
                if b['tickets'] != "[Ticket Number]":
                    consolidated_flights[f_key]['tickets'].extend([t.strip() for t in b['tickets'].split(',')])

            booking_details = ""
            all_unique_passengers = []
            all_raw_pnrs = []

            for flights_text, info in consolidated_flights.items():
                all_raw_pnrs.extend([p.split(" ")[0] for p in info['pnrs']])
                ref_label = "Booking References:" if len(info['pnrs']) > 1 else "Booking Reference:"
                joined_pnrs = ", ".join(info['pnrs'])
                
                unique_pax = list(dict.fromkeys(info['passengers'])) if info['passengers'] else ["[Passenger Names]"]
                joined_pax = ", ".join(unique_pax)
                all_unique_passengers.extend(unique_pax)
                
                unique_tkts = sorted(list(set(info['tickets'])))
                joined_tkts = ", ".join(unique_tkts) if unique_tkts else "[Ticket Number]"
                
                booking_details += f"{ref_label} {joined_pnrs}\nPassenger(s): {joined_pax}\nTicket Number(s): {joined_tkts}\nNew Travel Times:\n{flights_text}\n\n"

            global_unique_pax = list(dict.fromkeys(all_unique_passengers)) if all_unique_passengers else ["[Passenger Names]"]
            combined_passengers = ", ".join(global_unique_pax)
            all_pnrs = ", ".join(list(dict.fromkeys(all_raw_pnrs)))
            
            total_people = len(global_unique_pax)
            if total_people > 1: pronoun, client_word = "Their", "clients"
            else:
                client_word = "client"
                pronoun = "His" if "Mr." in combined_passengers else "Her" if ("Mrs." in combined_passengers or "Ms." in combined_passengers) else "Their"
                
            display_email = data['email'] if data['email'] else "[Email Address]"
            subject_line = f"Important Schedule Change: {combined_passengers} (Bookings: {all_pnrs})"
            
            if data['is_agency']:
                body_text = f"Dear {data['agency_name']} Team,\n\nPlease be advised of schedule changes affecting your {client_word}, {combined_passengers}. {pronoun} flights have been updated to the following:\n\n{booking_details}If you have not yet actioned this in your system, please secure these new flight times and reissue the ticket(s) at no additional cost. We also kindly ask that you inform the passenger(s) about this update.\n\nIf you require any assistance, please contact us at reservations@proflight-zambia.com or call us at +260971246950.\n\nKind regards,\n{agent_name}"
            else:
                body_text = f"Dear {combined_passengers},\n\nPlease be advised of schedule changes for your upcoming journey. Your flights have been updated to the following times:\n\n{booking_details}Your ticket(s) have already been updated at no additional cost, and your booking reference(s) remain valid. No further action is required on your part.\n\nIf you require any assistance, please contact us at reservations@proflight-zambia.com or call us at +260971246950.\n\nKind regards,\n{agent_name}"
            
            final_results.append({
                'to_email': display_email,
                'subject': subject_line,
                'body_text': body_text.strip(),
                'phone': data['phone'] if data['phone'] else "No Phone Listed",
                'warnings': list(set(data['warnings'])),
                'is_agency': data['is_agency'],
                'iata_no': data.get('iata_no', ''),
                'agency_name': data['agency_name'],
                'raw_email': data['email'],
                'raw_phone': data['phone']
            })

        return render(request, 'dashboard.html', {'final_results': final_results, 'missing_agencies': missing_agencies, 'raw_input': '', 'categorized_history': categorized_history})
        
    return render(request, 'dashboard.html', {'raw_input': '', 'categorized_history': categorized_history})


