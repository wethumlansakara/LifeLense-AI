"""Compare two TF-IDF classifiers on an explicitly synthetic starter dataset."""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.intelligence.text import preprocess

EXAMPLES = {
    'Food': ['breakfast sandwich meal', 'lunch rice curry meal', 'dinner noodles meal', 'dessert cake takeaway', 'fresh juice smoothie snack', 'burger fries takeaway', 'sushi dinner meal', 'pasta lunch meal', 'tea pastry snack', 'salad bowl lunch', 'roti takeaway snack', 'seafood dinner meal'],
    'Groceries': ['weekly vegetables market', 'household fruit produce', 'milk eggs bread basket', 'rice lentils pantry stock', 'fresh meat fish produce', 'weekly household staples', 'market fruit basket', 'kitchen ingredients produce', 'dairy bread staples', 'organic vegetables basket', 'household cereal supplies', 'pantry flour sugar stock'],
    'Transport': ['commute ride fare', 'railway season ticket', 'car parking charge', 'motorcycle petrol station', 'highway toll fee', 'airport shuttle ride', 'vehicle fuel refill', 'public transit fare', 'commute metro ticket', 'car diesel refill', 'scooter ride fare', 'road parking charge'],
    'Shopping': ['new jacket fashion', 'mobile phone accessories', 'home furniture order', 'laptop gadget order', 'sportswear fashion order', 'kitchen appliance order', 'new trousers fashion', 'headphones gadget order', 'office chair furniture', 'watch fashion accessories', 'handbag fashion order', 'camera gadget accessories'],
    'Entertainment': ['music subscription service', 'theatre performance tickets', 'gaming monthly subscription', 'amusement park tickets', 'comedy show tickets', 'museum admission tickets', 'live performance tickets', 'video subscription service', 'art exhibition admission', 'sports match admission', 'music festival tickets', 'game purchase digital'],
    'Bills': ['monthly broadband service', 'apartment lease payment', 'power supply charge', 'municipal water charge', 'mobile data plan', 'household gas charge', 'monthly cable service', 'telephone service charge', 'building maintenance fee', 'home power supply', 'monthly housing lease', 'sewerage service charge'],
    'Healthcare': ['prescription medicine refill', 'annual health checkup', 'clinic consultation fee', 'lab blood test', 'optical eye examination', 'physiotherapy treatment session', 'medicine prescription order', 'health vaccination fee', 'clinic treatment charge', 'laboratory screening charge', 'eye care consultation', 'medical diagnostic test'],
    'Education': ['semester learning fees', 'exam registration fee', 'learning workbook purchase', 'online training enrollment', 'language lesson fee', 'college enrollment charge', 'professional certification exam', 'learning materials purchase', 'training workshop fee', 'student semester fees', 'private lesson payment', 'academic registration fee'],
    'Travel': ['holiday accommodation stay', 'domestic air ticket', 'international vacation tour', 'guesthouse holiday stay', 'travel package deposit', 'vacation accommodation booking', 'weekend lodging charge', 'tour agency reservation', 'holiday guesthouse deposit', 'international air ticket', 'vacation package charge', 'travel accommodation payment'],
    'Other': ['charity donation transfer', 'family gift transfer', 'miscellaneous service charge', 'cash withdrawal machine', 'personal donation payment', 'community contribution gift', 'unspecified service payment', 'cash transfer personal', 'fundraising donation gift', 'miscellaneous cash charge', 'family contribution transfer', 'personal gift payment'],
}

def train():
    rows = [{'description': text, 'merchant': f'Synthetic merchant {category} {index}', 'category': category, 'provenance': 'synthetic starter example'} for category, texts in EXAMPLES.items() for index, text in enumerate(texts)]
    # Merchants are deliberately omitted from features so category-bearing synthetic names cannot leak labels.
    texts = [preprocess(row['description']) for row in rows]
    labels = [row['category'] for row in rows]
    indices = np.arange(len(rows))
    train_ids, test_ids = train_test_split(indices, test_size=.25, stratify=labels, random_state=42)
    candidates = {'logistic_regression': LogisticRegression(C=8, max_iter=1000, random_state=42), 'random_forest': RandomForestClassifier(n_estimators=150, random_state=42, class_weight='balanced', n_jobs=1)}
    scores, pipelines = {}, {}
    for name, classifier in candidates.items():
        model = Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)), ('classifier', classifier)])
        model.fit([texts[i] for i in train_ids], [labels[i] for i in train_ids])
        predicted = model.predict([texts[i] for i in test_ids])
        scores[name] = {'accuracy': accuracy_score([labels[i] for i in test_ids], predicted), 'macro_f1': f1_score([labels[i] for i in test_ids], predicted, average='macro', zero_division=0), 'report': classification_report([labels[i] for i in test_ids], predicted, output_dict=True, zero_division=0)}
        pipelines[name] = model
    winner = max(scores, key=lambda name: (scores[name]['macro_f1'], scores[name]['accuracy']))
    pipelines[winner].fit(texts, labels)
    output = ROOT / 'ml' / 'artifacts'
    output.mkdir(parents=True, exist_ok=True)
    metadata = {'trained_at': datetime.now(timezone.utc).isoformat(), 'selected_model': winner, 'samples': len(rows), 'held_out_samples': len(test_ids), 'dataset': 'synthetic starter examples', 'limitations': 'Holdout scores compare models on a small synthetic dataset only; they do not establish accuracy on real statements.', 'metrics': scores}
    joblib.dump({'pipeline': pipelines[winner], 'metadata': metadata}, output / 'category_model.joblib')
    (output / 'category_metrics.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    with (ROOT / 'ml' / 'data' / 'starter_categories.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['description', 'merchant', 'category', 'provenance']); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({key: value for key, value in metadata.items() if key != 'metrics'} | {'comparison': {name: {key: score[key] for key in ['accuracy', 'macro_f1']} for name, score in scores.items()}}, indent=2))

if __name__ == '__main__':
    (ROOT / 'ml' / 'data').mkdir(exist_ok=True)
    train()
