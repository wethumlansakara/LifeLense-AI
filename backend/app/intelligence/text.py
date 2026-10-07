import re
import unicodedata

MERCHANTS = {'uber': 'Transport', 'pickme': 'Transport', 'keells': 'Groceries', 'cargills': 'Groceries', 'netflix': 'Entertainment', 'spotify': 'Entertainment', 'dialog': 'Bills'}
KEYWORDS = {
    'Groceries': ['supermarket', 'groceries', 'grocery'],
    'Food': ['restaurant', 'cafe', 'coffee', 'pizza', 'bakery', 'dining'],
    'Transport': ['taxi', 'bus', 'fuel', 'petrol', 'train ticket'],
    'Bills': ['electricity', 'water bill', 'internet bill', 'utility', 'rent', 'mobitel'],
    'Healthcare': ['hospital', 'pharmacy', 'medical', 'doctor', 'dental'],
    'Education': ['school', 'tuition', 'university', 'course', 'textbook'],
    'Entertainment': ['cinema', 'movie', 'concert', 'streaming'],
    'Travel': ['hotel', 'airline', 'flight', 'booking', 'resort'],
    'Shopping': ['clothing', 'daraz', 'amazon', 'shoes', 'electronics'],
}

def preprocess(value):
    value = ''.join(character for character in unicodedata.normalize('NFKD', str(value or '')) if not unicodedata.combining(character)).casefold()
    value = re.sub(r'\b(?:pos|payment|purchase|transaction|ref|reference|lkr|rs)\b', ' ', value)
    return ' '.join(re.sub(r'[\W\d_]+', ' ', value).split())

def normalize_merchant(value):
    cleaned = preprocess(value)
    compact = cleaned.replace(' ', '')
    for merchant in MERCHANTS:
        # Match whole tokens/merchant prefixes, never "uber" inside "tuber".
        if re.search(r'\b' + re.escape(merchant) + r'\b', cleaned) or merchant == 'pickme' and compact.startswith('pickme'):
            return merchant
    return cleaned[:200]

def rule_category(description, merchant):
    canonical = normalize_merchant(merchant)
    if canonical in MERCHANTS:
        return MERCHANTS[canonical], .98, f'Known merchant: {canonical}.'
    text = preprocess(f'{merchant} {description}')
    for name, category in MERCHANTS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', text) or name == 'pickme' and 'pick me' in text:
            return category, .95, f'Matched merchant keyword: {name}.'
    matches = [(category, word) for category, words in KEYWORDS.items() for word in words if re.search(r'\b' + re.escape(word) + r'\b', text)]
    categories = {category for category, _ in matches}
    if len(categories) == 1:
        return matches[0][0], .85, f'Matched expense keyword: {matches[0][1]}.'
    return None
