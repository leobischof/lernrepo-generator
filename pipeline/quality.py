"""Separate source coverage and recorded reviews from mere JSON completion."""
from collections import defaultdict
from .io import digest, read, write
from .jobs import state


def audit(course):
    current = state(course)
    manifest = (current['manifest'] or {}).get('sources', {})
    index = read(course.path('job_index'), {})
    jobs = index.get('jobs', []) if index.get('state_hash') == digest(current) else []
    excluded = {(e['source'], e['page']) for e in (current['structure'] or {}).get('exclusions', [])
                if not e.get('text')}
    pages = {(s['source'], p) for s in (current['structure'] or {}).get('sections', [])
             for p in s['pages'] if (s['source'], p) not in excluded}
    cited = defaultdict(set)
    checked, blocked, self_checked, non_content = set(), [], set(), set()
    current_results, issues, fronts = 0, [], defaultdict(list)
    for job in jobs:
        result = read(course.path('results') / (job['job_id'] + '.json'), {})
        if result.get('input_hash') != job['input_hash']:
            continue
        current_results += 1
        for field in ('guide', 'cards', 'questions', 'audio', 'figures'):
            for item in result[field]:
                for ref in item['refs']:
                    cited[field].add((ref['source'], ref['page']))
                if field == 'cards':
                    fronts[' '.join(item['front'].casefold().split())].append(job['job_id'] + '/' + item['id'])
        if job['kind'] == 'script':
            if not result['guide']:
                issues.append({'job': job['job_id'], 'issue': 'empty-guide'})
            if 'cards' in job['products'] and not result['cards']:
                issues.append({'job': job['job_id'], 'issue': 'empty-cards'})
        review = read(course.path('quality_reviews') / (job['job_id'] + '.json'), {})
        if (review.get('input_hash') != job['input_hash']
                or review.get('result_hash') != digest(result) or not review.get('reviewer')):
            continue
        allowed = {(r['source'], r['page']) for r in job['sources']}
        for page in review.get('pages', []):
            key = page.get('source'), page.get('page')
            if (key not in allowed or not page.get('reason')
                    or page.get('source_sha256') != manifest.get(key[0], {}).get('sha256')):
                continue
            if page.get('status') == 'blocked':
                blocked.append({'source': key[0], 'page': key[1], 'reason': page['reason']})
            elif page.get('status') in {'covered', 'non-content'}:
                self_checked.add(key)
                # A model cannot promote its own work to an independently verified review.
                if review.get('verified') is True and review.get('verified_by'):
                    checked.add(key)
                    if page['status'] == 'non-content':
                        non_content.add(key)
    missing = sorted(pages - cited['guide'] - non_content)
    uncited = sorted(pages - set().union(*cited.values()))
    duplicates = [ids for ids in fronts.values() if len(ids) > 1]
    unreviewed = sorted(pages - checked)
    image_only = [{'source': sid, 'page': page} for sid, entry in manifest.items()
                  for page in entry.get('blank_pages', []) if (sid, page) not in excluded]
    serialize = lambda seq: [{'source': sid, 'page': page} for sid, page in seq]
    summary = dict(script_pages=len(pages), valid_results=current_results, planned_jobs=len(jobs),
                   reviewed_pages=len(pages & checked), worker_checked_pages=len(pages & self_checked),
                   missing_guide_pages=serialize(missing), uncited_pages=serialize(uncited),
                   unreviewed_pages=serialize(unreviewed), blocked_pages=blocked,
                   image_only_pages=image_only, issues=issues, duplicate_cards=duplicates,
                   ready=bool(jobs) and current_results == len(jobs) and not any(
                       (missing, unreviewed, blocked, image_only, issues, duplicates)))
    write(course.path('reports') / 'learning-quality.json', summary)
    text = '# Lernqualität\n\n'
    text += f"Formal gültige Antworten: {current_results}/{len(jobs)}. Das bestätigt keine fachliche Vollständigkeit.\n\n"
    text += f"Unabhängig geprüfte Skriptseiten: {summary['reviewed_pages']}/{len(pages)}. "
    text += f"AGY-/Modell-Selbstprüfung: {summary['worker_checked_pages']} Seiten.\n\n"
    text += f"Freigabestatus: {'geprüft' if summary['ready'] else 'offen'}.\n\n"
    for title, entries in [('Ohne Leitfadenbeleg', summary['missing_guide_pages']),
                           ('Ohne jeglichen Produktverweis', summary['uncited_pages']),
                           ('Textlose Quellen', image_only), ('Blockierte Seiten', blocked)]:
        text += '## ' + title + '\n\n'
        text += '\n'.join('- ' + x['source'] + ', PDF S. ' + str(x['page']) +
                          (': ' + x['reason'] if 'reason' in x else '') for x in entries) or 'Keine.'
        text += '\n\n'
    text += 'Ein Quellenverweis allein beweist nicht, dass alle Listen, Tabellen, Formeln oder Bildinhalte übernommen wurden.\n'
    write(course.path('reports') / 'learning-quality.md', text)
    return summary
