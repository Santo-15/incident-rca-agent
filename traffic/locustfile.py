import random
from locust import HttpUser, between, task
MAX_PRODUCT_ID = 50
MISSING_PRODUCT_ID = 999999

class Shopper(HttpUser):                        
    wait_time = between(1, 3)                   
    def on_start(self):                         
        self.user_id = random.randint(1, 1000)

    @task(6)                                    
    def browse(self):
        params = {"limit": 10}                 
        if random.random() < 0.3:               
            params["sort"] = "price"            
        self.client.get("/products", params=params, name="/products")

    @task(3)                                    
    def view_product(self):
        product_id = random.randint(1, MAX_PRODUCT_ID) if random.random() < 0.9 else MISSING_PRODUCT_ID  
        with self.client.get(f"/products/{product_id}", name="/products/[id]", catch_response=True) as resp:  
            if resp.status_code in (200, 404):  
                resp.success()                  
            else:
                resp.failure(f"unexpected status {resp.status_code}")

    @task(2)                                    
    def add_to_cart(self):
        body = {"product_id": random.randint(1, MAX_PRODUCT_ID), "qty": random.randint(1, 3)}  
        self.client.post(f"/users/{self.user_id}/cart", json=body, name="/users/[id]/cart")

    @task(1)                                    
    def checkout(self):
        with self.client.post(f"/users/{self.user_id}/checkout", name="/users/[id]/checkout", catch_response=True) as resp:
            if resp.status_code in (201, 400):  
                resp.success()                  
            else:
                resp.failure(f"unexpected status {resp.status_code}")  