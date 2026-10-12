import argparse
import random

from sqlalchemy import func, insert, select
from app.db import SessionLocal, engine
from app.models import Base, Product

BASE_PRODUCTS = [
    {"name": "T-shirt", "price": 499},  # id 1 on a fresh table
    {"name": "Jeans", "price": 1299},  # id 2: the product we always add to user 7's cart
    {"name": "Cap", "price": 299},  # id 3
]

def main():
    parser = argparse.ArgumentParser(description="Fill the shop database with products")  
    parser.add_argument(
        "--reset",  
        action="store_true",  
        help="drop and recreate all tables first (deletes carts and orders too)",  
    )
    parser.add_argument(  
        "--extra",  
        type=int,  
        default=0,  
        help="how many extra generated products to add (for realistic slow_query tests)",
    )
    args = parser.parse_args() 

    if args.reset:  
        Base.metadata.drop_all(engine)  
    Base.metadata.create_all(engine)  

    with SessionLocal() as db:  
        count = db.scalar(select(func.count()).select_from(Product))  
        if count > 0:  
            print(f"products already has {count} rows, nothing to do (use --reset to start over)")  
            return  

        db.execute(insert(Product), BASE_PRODUCTS)  

        if args.extra > 0:  
            random.seed(42)  
            rows = [  
                {"name": f"Item {i}", "price": random.randint(100, 5000)}  
                for i in range(1, args.extra + 1)  
            ]
            db.execute(insert(Product), rows)  

        db.commit()  
        total = db.scalar(select(func.count()).select_from(Product))  
        print(f"seeded {total} products")  

if __name__ == "__main__":  
    main()  