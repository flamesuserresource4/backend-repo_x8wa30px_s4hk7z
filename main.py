import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from bson import ObjectId

from schemas import (
    Product,
    Customization,
    Order,
    ChatRequest,
    RecommendationRequest,
)
from database import db, create_document, get_documents

app = FastAPI(title="Vintage Clothier API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Vintage Clothier API running"}


@app.get("/schema")
def get_schema():
    # Expose minimal schema metadata for viewer tools
    from schemas import (
        Product,
        Customization,
        Order,
    )
    return {
        "models": {
            "product": Product.model_json_schema(),
            "customization": Customization.model_json_schema(),
            "order": Order.model_json_schema(),
        }
    }


# ---------------------- Products ----------------------
@app.post("/products")
def create_product(product: Product):
    try:
        _id = create_document("product", product)
        return {"id": _id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products")
def list_products(category: Optional[str] = Query(None), limit: int = Query(50)):
    try:
        filt: Dict[str, Any] = {}
        if category:
            filt["category"] = category
        items = get_documents("product", filt, limit)
        for it in items:
            it["id"] = str(it.pop("_id")) if "_id" in it else None
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------- Customization ----------------------

def auto_complete_customization(cust: Customization, product: Optional[dict]) -> Dict[str, Any]:
    # Simple rule engine to auto-complete choices
    result = cust.model_dump()
    category = cust.category

    # Defaults based on category if missing
    defaults = {
        "suit": {"fit": "tailored", "fabric": "worsted wool", "color": "navy", "pattern": "solid"},
        "boots": {"color": "oxblood", "fabric": "full-grain leather", "fit": "regular"},
        "shoes": {"color": "chestnut", "fabric": "calf leather", "fit": "regular"},
        "hat": {"color": "charcoal", "fabric": "felt", "pattern": "solid"},
        "belt": {"color": "dark brown", "fabric": "leather"},
        "shirt": {"color": "white", "fabric": "oxford", "fit": "slim"},
        "trousers": {"color": "charcoal", "fabric": "wool", "fit": "classic"},
    }

    base = defaults.get(category, {})

    # Pull available options from product if provided
    if product:
        for key in ["color", "fabric", "size", "fit", "pattern"]:
            if not result.get(key):
                options = product.get(key + "s") if key + "s" in product else product.get(key)
                if isinstance(options, list) and options:
                    result[key] = options[0]

    # Apply defaults for any missing
    for k, v in base.items():
        result[k] = result.get(k) or v

    # Simple size inference
    m = cust.measurements
    if not result.get("size") and m and m.chest_cm:
        if m.chest_cm < 90:
            result["size"] = "XS"
        elif m.chest_cm < 96:
            result["size"] = "S"
        elif m.chest_cm < 102:
            result["size"] = "M"
        elif m.chest_cm < 110:
            result["size"] = "L"
        else:
            result["size"] = "XL"

    # Estimate price
    base_price = product.get("base_price", 300) if product else 300
    multipliers = 1.0
    if result.get("fabric"):
        fab = result["fabric"].lower()
        if "cashmere" in fab:
            multipliers += 0.6
        elif "wool" in fab:
            multipliers += 0.25
        elif "leather" in fab:
            multipliers += 0.35
        elif "linen" in fab:
            multipliers += 0.15
    if result.get("pattern") and result["pattern"].lower() in ["pinstripe", "herringbone", "houndstooth"]:
        multipliers += 0.1
    if result.get("fit") and result["fit"].lower() in ["tailored", "slim"]:
        multipliers += 0.05

    est_price = round(base_price * multipliers, 2)

    return {"config": result, "est_price": est_price}


@app.post("/customize")
def customize(cust: Customization):
    # Load product if provided
    product = None
    if cust.product_id:
        try:
            oid = ObjectId(cust.product_id)
            product = db["product"].find_one({"_id": oid})
            if product:
                product["id"] = str(product.pop("_id"))
        except Exception:
            product = None
    data = auto_complete_customization(cust, product)
    return data


# ---------------------- Orders ----------------------
@app.post("/orders")
def create_order(order: Order):
    try:
        _id = create_document("order", order)
        return {"id": _id, "status": "received"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders")
def list_orders(limit: int = 50):
    try:
        items = get_documents("order", {}, limit)
        for it in items:
            it["id"] = str(it.pop("_id")) if "_id" in it else None
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------- Recommendations ----------------------
@app.post("/recommendations")
def recommendations(req: RecommendationRequest):
    # Filter products by category or tags/colors if provided
    filt: Dict[str, Any] = {}
    if req.category:
        filt["category"] = req.category
    products = get_documents("product", filt, 50)

    # If no products seeded yet, provide virtual suggestions
    if not products:
        seed = [
            {"title": "Savile Row Three-Piece Suit", "category": "suit", "base_price": 1200},
            {"title": "Full-Grain Leather Boots", "category": "boots", "base_price": 380},
            {"title": "Classic Oxford Shirt", "category": "shirt", "base_price": 120},
        ]
        products = seed

    # Basic ranking by budget/style
    out = []
    for p in products[:6]:
        cust = Customization(category=p.get("category", req.category or "suit"))
        comp = auto_complete_customization(cust, p)
        price = comp["est_price"]
        if req.budget and price > req.budget * 1.2:
            continue
        rationale = "Balanced choice with premium materials"
        if req.style and req.style.lower() in ["vintage", "classic"]:
            rationale = "Vintage-forward aesthetic with timeless details"
        if req.purpose and "wedding" in req.purpose.lower():
            rationale = "Formal-appropriate with elevated finishing"
        out.append({
            "product_id": str(p.get("_id")) if p and p.get("_id") else None,
            "title": p.get("title"),
            "category": p.get("category"),
            "suggested_config": comp["config"],
            "est_price": comp["est_price"],
            "rationale": rationale,
        })
        if len(out) >= 3:
            break

    return {"recommendations": out}


# ---------------------- Chat (rule-based) ----------------------
@app.post("/chat")
def chat(req: ChatRequest):
    # Very simple rule-based assistant to guide selection
    user_texts = [m.content for m in req.messages if m.role == "user"]
    last = (user_texts[-1] if user_texts else "").lower()

    # Detect category intent
    cat_map = {
        "suit": ["suit", "tux", "blazer"],
        "boots": ["boot"],
        "shoes": ["shoe", "oxford", "derby", "loafer"],
        "hat": ["hat", "fedora", "trilby"],
        "belt": ["belt"],
        "shirt": ["shirt", "oxford"],
        "trousers": ["trouser", "pant", "slacks"],
    }
    chosen = None
    for k, kws in cat_map.items():
        if any(w in last for w in kws):
            chosen = k
            break

    if chosen:
        rec = recommendations(RecommendationRequest(category=chosen, style="vintage"))
        msg = f"I recommend these {chosen} options. Would you like me to tailor the fit and fabric to your climate and occasion?"
        return {"reply": msg, "data": rec}

    if any(w in last for w in ["wedding", "business", "casual", "black tie"]):
        purpose = "wedding" if "wedding" in last else ("business" if "business" in last else "casual")
        rec = recommendations(RecommendationRequest(purpose=purpose, style="classic"))
        return {"reply": f"Here are refined picks for {purpose}.", "data": rec}

    return {"reply": "Tell me what you're looking for (e.g., a navy suit for a wedding, leather boots for winter). I'll recommend configs and pricing.", "data": {}}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
