# shopify_insights_api.py
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
import re
from typing import List, Optional
import uvicorn

app = FastAPI()

class Product(BaseModel):
    title: str
    handle: str
    product_type: Optional[str]
    price: Optional[str] = None

class BrandInsights(BaseModel):
    brand_url: HttpUrl
    products: List[Product]
    hero_products: List[str]
    privacy_policy: Optional[str]
    return_policy: Optional[str]
    faqs: List[str]
    social_links: List[HttpUrl]
    contact_emails: List[str]
    contact_phones: List[str]
    about_text: Optional[str]
    important_links: List[HttpUrl]

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <body>
            <h2>Shopify Store Insights Fetcher</h2>
            <form action="/submit" method="post">
                <label>Enter Shopify Store URL:</label>
                <input type="text" name="url" style="width:300px">
                <button type="submit">Fetch Insights</button>
            </form>
        </body>
    </html>
    """

@app.post("/submit", response_class=HTMLResponse)
def submit(url: str = Form(...)):
    try:
        insights = fetch_brand_insights(url)
        return f"<pre>{insights.json(indent=2)}</pre>"
    except HTTPException as e:
        return f"<h3>Error {e.status_code}: {e.detail}</h3>"

@app.get("/fetch_insights", response_model=BrandInsights)
def fetch_insights(website_url: HttpUrl):
    return fetch_brand_insights(website_url)

def fetch_brand_insights(website_url: str) -> BrandInsights:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(str(website_url), headers=headers, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Website not reachable or not found")

        soup = BeautifulSoup(resp.text, 'html.parser')

        try:
            products_data = requests.get(f"{website_url}/products.json", timeout=10).json()
            products = [
                Product(
                    title=item["title"],
                    handle=item["handle"],
                    product_type=item.get("product_type"),
                    price=item["variants"][0].get("price") if item.get("variants") else None
                ) for item in products_data.get("products", [])
            ]
        except Exception:
            products = []

        hero_products = list(set(
            [tag.get_text(strip=True) for tag in soup.select('a[href*="/products/"]')][:5]
        ))

        def extract_policy_text(path: str) -> Optional[str]:
            try:
                pol = requests.get(f"{website_url}/{path}", timeout=10).text
                return BeautifulSoup(pol, 'html.parser').get_text(" ", strip=True)[:1000]
            except:
                return None

        privacy_policy = extract_policy_text("policies/privacy-policy")
        return_policy = extract_policy_text("policies/refund-policy")

        faqs = [faq.get_text(" ", strip=True) for faq in soup.find_all(string=re.compile(r'Q[:)?]|FAQ', re.I))]

        social_links = [
            HttpUrl(url, scheme='https') for url in re.findall(r'https?://(?:www\.)?(instagram|facebook|tiktok)\.com/[^"\s<>]+', resp.text)
        ]

        contact_emails = list(set(re.findall(r'[\w\.-]+@[\w\.-]+', resp.text)))
        contact_phones = list(set(re.findall(r'\+?[\d\s\-]{10,15}', resp.text)))

        about = soup.find("section", string=re.compile("about", re.I)) or soup.find("p", string=re.compile("about", re.I))
        about_text = about.get_text(strip=True) if about else None

        important_keywords = ["track", "contact", "blog"]
        important_links = [
            HttpUrl(a["href"], scheme='https') if a["href"].startswith("http") else HttpUrl(f"{website_url}{a['href']}", scheme='https')
            for a in soup.find_all("a", href=True)
            if any(k in a["href"].lower() for k in important_keywords)
        ]

        return BrandInsights(
            brand_url=website_url,
            products=products,
            hero_products=hero_products,
            privacy_policy=privacy_policy,
            return_policy=return_policy,
            faqs=faqs,
            social_links=social_links,
            contact_emails=contact_emails,
            contact_phones=contact_phones,
            about_text=about_text,
            important_links=important_links
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("shopify_insights_api:app", host="127.0.0.1", port=8000, reload=True)
