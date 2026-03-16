import json
import datetime
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from .models import Person, Attribute
from .services.importer import read_file, detect_mapping, import_dataframe
from .services.nenki_calculator import get_anniversaries_for_year
from .services.document_generator import DocumentGenerator
from .services.date_converter import format_date_kanji_era


def index(request):
    return render(request, 'memorial/index.html')


# ── People ────────────────────────────────────────────────────────────────────

def people_list(request):
    if request.method == 'GET':
        q = request.GET.get('q', '').strip()
        qs = Person.objects.prefetch_related('attributes').all()
        if q:
            qs = qs.filter(name__icontains=q)
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        total = qs.count()
        people = qs[(page - 1) * per_page: page * per_page]
        data = []
        for p in people:
            attrs = p.get_attributes()
            data.append({'id': p.id, 'name': p.name, 'death_date': p.death_date, **attrs})
        return JsonResponse({'total': total, 'page': page, 'per_page': per_page, 'people': data})

    if request.method == 'POST':
        body = json.loads(request.body)
        p = Person.objects.create(
            name=body['name'],
            death_date=body['death_date'],
        )
        for k, v in body.get('attributes', {}).items():
            Attribute.objects.create(person=p, column_name=k, value=v)
        return JsonResponse({'id': p.id}, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_http_methods(['GET', 'PUT', 'DELETE'])
def person_detail(request, pk):
    try:
        p = Person.objects.prefetch_related('attributes').get(pk=pk)
    except Person.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        attrs = p.get_attributes()
        return JsonResponse({'id': p.id, 'name': p.name, 'death_date': p.death_date, **attrs})

    if request.method == 'PUT':
        body = json.loads(request.body)
        p.name = body.get('name', p.name)
        p.death_date = body.get('death_date', p.death_date)
        p.save()
        if 'attributes' in body:
            p.attributes.all().delete()
            for k, v in body['attributes'].items():
                Attribute.objects.create(person=p, column_name=k, value=v)
        return JsonResponse({'id': p.id})

    if request.method == 'DELETE':
        p.delete()
        return JsonResponse({'deleted': pk})


# ── Import ────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def import_preview(request):
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    f = request.FILES['file']
    try:
        sheets = read_file(f, f.name)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    result = {}
    for sheet_name, df in sheets.items():
        cols = list(df.columns)
        mapping = detect_mapping(cols)
        preview_rows = df.head(5).fillna('').to_dict(orient='records')
        result[sheet_name] = {'columns': cols, 'mapping': mapping, 'preview': preview_rows}
    return JsonResponse({'sheets': result})


@csrf_exempt
@require_http_methods(['POST'])
def import_confirm(request):
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    f = request.FILES['file']
    mapping_raw = request.POST.get('mapping', '{}')
    sheet_name = request.POST.get('sheet', None)
    try:
        mapping = json.loads(mapping_raw)
        sheets = read_file(f, f.name)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    df = sheets.get(sheet_name) if sheet_name and sheet_name in sheets else list(sheets.values())[0]
    entries = import_dataframe(df, mapping)
    created = 0
    errors = []
    for entry in entries:
        if not entry['name'] or not entry['death_date']:
            errors.append({'name': entry.get('name', ''), 'errors': entry.get('errors', [])})
            continue
        p, is_new = Person.objects.get_or_create(
            name=entry['name'], death_date=entry['death_date'],
            defaults={'source_file': f.name}
        )
        if is_new:
            for k, v in entry.get('attributes', {}).items():
                Attribute.objects.create(person=p, column_name=k, value=v)
            created += 1

    return JsonResponse({'created': created, 'skipped': len(entries) - created, 'errors': errors})


# ── Calculate ─────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(['POST'])
def calculate(request):
    body = json.loads(request.body)
    target_year = int(body.get('year', datetime.date.today().year))

    if body.get('all'):
        people = list(Person.objects.prefetch_related('attributes').all())
    else:
        ids = body.get('person_ids', [])
        people = list(Person.objects.prefetch_related('attributes').filter(id__in=ids))

    groups = {}
    all_fields = {'name', 'death_date_kanji', 'anniversary_date_kanji', '年忌名'}

    for person in people:
        try:
            death_date = datetime.date.fromisoformat(person.death_date)
        except (ValueError, TypeError):
            continue
        anniversaries = get_anniversaries_for_year(death_date, target_year)
        attrs = person.get_attributes()
        all_fields.update(attrs.keys())

        for ann in anniversaries:
            key = f"{ann.name}|{ann.years_offset}"
            entry = {
                'person_id': person.id,
                'name': person.name,
                'death_date_kanji': format_date_kanji_era(death_date),
                'anniversary_date_kanji': format_date_kanji_era(ann.date),
                '年忌名': ann.name,
                **attrs,
            }
            groups.setdefault(key, []).append(entry)

    def sort_key(item):
        try:
            return int(item[0].split('|')[1])
        except Exception:
            return 0

    sorted_groups = sorted(groups.items(), key=sort_key)

    return JsonResponse({
        'year': target_year,
        'groups': [{'key': k, 'nenki_name': v[0]['年忌名'] if v else '', 'entries': v}
                   for k, v in sorted_groups],
        'available_fields': sorted(all_fields),
        'total_entries': sum(len(v) for _, v in sorted_groups),
    })


# ── Generate ──────────────────────────────────────────────────────────────────

def _parse_generate_request(request):
    body = json.loads(request.body)
    layout = body.get('layout', {})
    groups_raw = body.get('groups', [])
    selected_fields = body.get('selected_fields', [])
    sorted_data = [(g['key'], g['entries']) for g in groups_raw]
    return layout, sorted_data, selected_fields


@csrf_exempt
@require_http_methods(['POST'])
def generate_word(request):
    layout, sorted_data, fields = _parse_generate_request(request)
    gen = DocumentGenerator(layout)
    docx_bytes = gen.generate_word(sorted_data, fields)
    response = HttpResponse(
        docx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = 'attachment; filename="nenki.docx"'
    return response


@csrf_exempt
@require_http_methods(['POST'])
def generate_pdf(request):
    layout, sorted_data, fields = _parse_generate_request(request)
    gen = DocumentGenerator(layout)
    pdf_bytes = gen.generate_pdf(sorted_data, fields)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="nenki.pdf"'
    return response
