from sqlalchemy.dialects.postgresql import insert
from .database import SessionLocal
from .models import Category

CATEGORIES = [('Food', 'utensils'), ('Groceries', 'basket'), ('Transport', 'bus'), ('Shopping', 'bag'), ('Entertainment', 'film'), ('Bills', 'receipt'), ('Healthcare', 'heart'), ('Education', 'book'), ('Travel', 'plane'), ('Salary', 'wallet'), ('Other', 'circle')]

def seed():
    with SessionLocal() as db:
        for name, icon in CATEGORIES:
            db.execute(insert(Category).values(name=name, icon=icon, type='income' if name == 'Salary' else 'expense').on_conflict_do_nothing(index_elements=['name']))
        db.commit()

if __name__ == '__main__':
    seed()
