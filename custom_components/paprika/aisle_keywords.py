"""Keyword fallback for guessing a Paprika aisle from an item name.

Items created through the sync API are stored with no aisle, and Paprika's apps
show them under Miscellaneous. Paprika's own aisle guess presumably happens
client-side in the apps, or in an undocumented server-side process; either way it
isn't applied to items we post. This table is a workaround that guesses an aisle
ourselves. Keys are Paprika's default aisle names; aisles the user has renamed or
removed are skipped. The longest matching keyword wins; ties go to the aisle listed
first.
"""

import re

AISLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Frozen Foods": ("frozen", "ice cream", "popsicle", "pizza rolls", "waffles"),
    "Baby Products": ("diaper", "baby", "wipes", "formula"),
    "Pet Products": ("dog food", "cat food", "cat litter", "pet", "treats for"),
    "Cleaning Supplies": (
        "detergent", "bleach", "dish soap", "sponge", "trash bag", "garbage bag",
        "cleaner", "windex", "laundry", "dishwasher",
    ),
    "Health and Beauty": (
        "toothpaste", "toothbrush", "shampoo", "conditioner", "deodorant",
        "soap", "razor", "lotion", "sunscreen", "floss", "vitamin", "tylenol",
        "advil", "band-aid", "tampon",
    ),
    "Home and Garden": (
        "paper towel", "toilet paper", "tissue", "napkin", "light bulb",
        "battery", "batteries", "aluminum foil", "plastic wrap", "ziploc",
        "parchment", "candle", "foil",
    ),
    "Beer, Wine and Spirits": (
        "beer", "wine", "vodka", "whiskey", "bourbon", "gin", "rum", "tequila",
        "liquor", "prosecco", "champagne",
    ),
    "Seafood": (
        "salmon", "shrimp", "tuna steak", "cod", "tilapia", "scallop", "lobster",
        "crab", "halibut", "fish", "mussels", "clams", "trout", "mahi",
    ),
    "Meat": (
        "chicken", "beef", "pork", "turkey", "steak", "bacon", "sausage", "ham",
        "ground", "lamb", "ribs", "brisket", "pancetta", "meatball", "hot dog",
    ),
    "Deli": ("deli", "prosciutto", "salami", "pepperoni", "lunch meat", "hummus"),
    "Dairy": (
        "milk", "cheese", "butter", "yogurt", "yoghurt", "cream", "egg", "eggs",
        "sour cream", "mozzarella", "parmesan", "cheddar", "feta", "ricotta",
        "half and half", "creamer", "kefir",
    ),
    "Bakery": ("bakery", "croissant", "bagel", "muffin", "donut", "doughnut", "cake", "baguette", "roll", "rolls"),
    "Breads and Cereals": (
        "bread", "cereal", "oatmeal", "granola", "tortilla", "bun", "buns",
        "pita", "english muffin", "wrap", "taco shell",
    ),
    "Produce": (
        "apple", "banana", "orange", "lemon", "lime", "berries", "strawberr",
        "blueberr", "raspberr", "grape", "avocado", "tomato", "onion", "garlic",
        "potato", "carrot", "celery", "lettuce", "spinach", "kale", "cucumber",
        "pepper", "broccoli", "cauliflower", "zucchini", "squash", "mushroom",
        "cabbage", "cilantro", "parsley", "basil", "mint", "herb", "ginger",
        "melon", "pear", "peach", "mango", "pineapple", "salad", "asparagus",
        "corn", "beet", "radish", "scallion", "shallot", "jalapeno", "arugula",
    ),
    "Pasta, Rice and Beans": (
        "pasta", "spaghetti", "penne", "macaroni", "noodle", "rice", "beans",
        "lentil", "quinoa", "couscous", "orzo", "chickpea",
    ),
    "Spices and Seasonings": (
        "spice", "seasoning", "cumin", "paprika", "oregano", "thyme", "cinnamon",
        "salt", "black pepper", "chili powder", "garlic powder", "onion powder",
        "cayenne", "turmeric", "nutmeg", "bay leaves", "rosemary",
    ),
    "Oils and Dressings": (
        "olive oil", "vegetable oil", "canola", "cooking spray", "dressing",
        "vinaigrette", "vinegar", "sesame oil", "oil",
    ),
    "Sauces and Condiments": (
        "ketchup", "mustard", "mayo", "mayonnaise", "sauce", "salsa", "bbq",
        "hot sauce", "soy sauce", "relish", "pickle", "jam", "jelly", "honey",
        "syrup", "peanut butter", "worcestershire", "sriracha",
    ),
    "Baking Goods": (
        "flour", "sugar", "baking soda", "baking powder", "yeast", "vanilla",
        "chocolate chips", "cocoa", "cornstarch", "sprinkles", "extract",
    ),
    "Canned and Jar Goods": (
        "canned", "can of", "soup", "broth", "stock", "tomato paste",
        "diced tomatoes", "crushed tomatoes", "chicken broth", "beef broth",
        "chicken stock", "beef stock", "vegetable broth", "olives", "tuna", "capers",
    ),
    "Snacks": (
        "chips", "tortilla chips", "crackers", "pretzel", "popcorn", "cookies", "candy", "nuts",
        "almonds", "cashews", "trail mix", "chocolate", "granola bar", "snack",
    ),
    "Beverages": (
        "water", "juice", "soda", "coffee", "tea", "sparkling", "seltzer",
        "kombucha", "ginger beer", "ginger ale", "lemonade", "gatorade", "cola", "energy drink",
    ),
    "International Cuisine": (
        "tahini", "miso", "kimchi", "curry paste", "coconut milk", "rice paper",
        "nori", "tofu", "sambal", "gochujang", "naan",
    ),
}


def guess_aisle_name(item: str, available: set[str]) -> str | None:
    """Return the available aisle whose longest keyword appears in `item`.

    Longest keyword wins so "peanut butter" beats "butter"; ties go to the aisle
    listed first in AISLE_KEYWORDS.
    """
    text = item.strip().lower()
    best: tuple[int, str] | None = None
    for aisle, keywords in AISLE_KEYWORDS.items():
        if aisle not in available:
            continue
        for keyword in keywords:
            # Short keywords match whole words (plus s/es) so "gin" doesn't hit
            # "ginger"; longer ones match a word prefix so "strawberr" hits
            # "strawberries".
            if len(keyword) <= 4:
                pattern = rf"\b{re.escape(keyword)}(?:s|es)?\b"
            else:
                pattern = rf"\b{re.escape(keyword)}"
            if re.search(pattern, text) and (best is None or len(keyword) > best[0]):
                best = (len(keyword), aisle)
    return best[1] if best else None
