from typing import List

# Extended list of common MCCs. Edit or prune as needed.
MCC_CODES: List[int] = [
    # Grocery & Food
    5411,  # Grocery Stores, Supermarkets
    5422,  # Freezer & Locker Meat Provisioners
    5499,  # Miscellaneous Food Stores—Convenience Stores and Specialty Markets
    5921,  # Package Stores, Beer, Wine, and Liquor
    5812,  # Eating Places, Restaurants
    5813,  # Bars, Cocktail Lounges, Discotheques, Nightclubs, Taverns
    5814,  # Fast Food Restaurants
    5451,  # Dairy Products Stores
    5462,  # Bakeries
    # Retail (Apparel, Electronics, Department)
    5651,  # Family Clothing Stores
    5691,  # Men’s and Boys’ Clothing and Accessories Stores
    5699,  # Miscellaneous Apparel and Accessory Shops
    5311,  # Department Stores
    5331,  # Variety Stores (e.g., 5 & 10, Dollar Stores)
    5399,  # Miscellaneous General Merchandise
    5732,  # Electronics Stores
    5733,  # Music Stores, Musical Instruments
    5931,  # Used Merchandise and Secondhand Stores
    5940,  # Bicycle Shops—Sales and Service
    5942,  # Book Stores
    5943,  # Office, School Supply, and Stationery Stores
    5944,  # Jewelry, Watch, Clock, and Silverware Stores
    5945,  # Hobby, Toy, & Game Shops
    5946,  # Camera and Photographic Supply Stores
    5947,  # Gift, Card, Novelty, and Souvenir Shops
    5948,  # Luggage and Leather Goods Stores
    5949,  # Fabric Stores, Piece Goods, and Sewing Notions
    5600,  # Apparel and Accessory Services (Cleaning, Alterations, etc.)
    # Home & Hardware
    5211,  # Lumber and Building Materials Stores, Hardware
    5251,  # Hardware Stores
    5261,  # Lawn and Garden Supply Stores
    5712,  # Furniture, Home Furnishings, and Equipment Stores
    5722,  # Household Appliance Stores
    5734,  # Computer Software Stores
    5735,  # Record Stores, Video Tapes, and Disks
    5970,  # Artist Supply and Craft Shops
    # Health & Beauty
    5912,  # Drug Stores and Pharmacies
    5971,  # Electrical and Electronic Repair Shops
    5972,  # Stamp and Coin Stores
    5975,  # Hearing Aids—Sales and Service
    5977,  # Cosmetic Stores
    5978,  # Typewriter Stores—Sales, Service, and Supplies
    5913,  # Packaged Liquor Stores
    5973,  # Antiquarian and Specialty Collectible Stores
    5974,  # Computer Network/Information Services
    # Transportation & Travel
    4111,  # Local/Suburban Commuter Passenger Transport (Including Ferries)
    4121,  # Taxicabs and Limousines
    4131,  # Bus Lines, Motor Bus Lines, and Charters
    4411,  # Cruise Lines
    4457,  # Boat Rentals and Leases
    4468,  # Marinas, Marine Service and Supplies
    4511,  # Airlines, Air Carriers
    4784,  # Tolls and Bridge Fees
    4812,  # Telecommunication Equipment and Telephone Sales
    4789,  # Transportation Services (Not Elsewhere Classified)
    7512,  # Automobile Rental Agencies
    7513,  # Automobile Parking Lots and Garages
    7519,  # Motor Home Rental
    # Lodging & Entertainment
    5811,  # Caterers
    7011,  # Hotels, Motels, Resorts (Lodging)
    7022,  # Sporting and Recreational Camps
    7032,  # Amusement Parks
    7033,  # Campgrounds and Trailer Parks
    7210,  # Laundry, Cleaning, and Garment Services
    7211,  # Laundry Services
    7216,  # Dry Cleaners
    7230,  # Beauty and Barber Shops
    7297,  # Massage Parlors, Sauna and Steam Baths
    7298,  # Health and Beauty Spas
    7311,  # Advertising Services—Outdoor Advertising, Posters
    7321,  # Consumer Credit Reporting Agencies, Credit Bureaus
    7322,  # Debt Collection Agencies
    7338,  # Quick Copy, Reproduction, and Blueprinting Services
    7339,  # Stenographic and Secretarial Support Services
    7342,  # Exterminating and Disinfecting Services
    7349,  # Cleaning and Maintenance, Janitorial Services
    7511,  # Truck Stop (Truck Parking, Supplies and Services)
    7995,  # Gambling—Casinos, Race Tracks
    # Professional & Business Services
    8011,  # Doctors and Physicians
    8021,  # Dentists and Orthodontists
    8031,  # Osteopaths
    8041,  # Chiropractors
    8042,  # Optometrists, Ophthalmologist’s Services
    8043,  # Opticians, Optical Goods, and Eyeglasses
    8049,  # Podiatrists
    8050,  # Nursing and Personal Care Facilities
    8062,  # Hospitals
    8099,  # Medical Services (Not Elsewhere Classified)
    8111,  # Legal Services and Attorneys
    8211,  # Elementary and Secondary Schools
    8220,  # Colleges, Universities, Professional Schools
    8241,  # Correspondence Schools
    8244,  # Business and Secretarial Schools
    8249,  # Vocational and Trade Schools
    8299,  # Schools and Educational Services (Not Elsewhere Classified)
    8398,  # Charitable and Social Service Organizations
    8661,  # Religious Organizations
    # Government & Misc
    9211,  # Court Costs, Including Alimony and Child Support
    9222,  # Fines
    9311,  # Tax Payments
    9399,  # Government Services (Not Elsewhere Classified)
    9402,  # Postal Services—Government Only
]


# Industry-average chargeback rates by category (decimal form)
MCC_CODE_WEIGHTS: List[float] = [
    # Grocery & Food (Retail) – 0.52%
    0.0052,  # 5411 Grocery Stores, Supermarkets
    0.0052,  # 5422 Freezer & Locker Meat Provisioners
    0.0052,  # 5499 Miscellaneous Food Stores—Convenience & Specialty Markets
    0.0052,  # 5921 Package Stores, Beer, Wine, and Liquor
    # Restaurants & Bars – 0.12%
    0.0012,  # 5812 Eating Places, Restaurants
    0.0012,  # 5813 Bars, Cocktail Lounges, Discotheques, Nightclubs, Taverns
    0.0012,  # 5814 Fast Food Restaurants
    # Dairy & Bakeries (Retail) – 0.52%
    0.0052,  # 5451 Dairy Products Stores
    0.0052,  # 5462 Bakeries
    # Apparel & Specialty Retail – 0.52%
    0.0052,  # 5651 Family Clothing Stores
    0.0052,  # 5691 Men’s and Boys’ Clothing and Accessories Stores
    0.0052,  # 5699 Miscellaneous Apparel and Accessory Shops
    0.0052,  # 5311 Department Stores
    0.0052,  # 5331 Variety Stores (e.g., 5 & 10, Dollar Stores)
    0.0052,  # 5399 Miscellaneous General Merchandise
    0.0052,  # 5732 Electronics Stores
    0.0052,  # 5733 Music Stores, Musical Instruments
    0.0052,  # 5931 Used Merchandise and Secondhand Stores
    0.0052,  # 5940 Bicycle Shops—Sales and Service
    0.0052,  # 5942 Book Stores
    0.0052,  # 5943 Office, School Supply, and Stationery Stores
    0.0052,  # 5944 Jewelry, Watch, Clock, and Silverware Stores
    0.0052,  # 5945 Hobby, Toy, & Game Shops
    0.0052,  # 5946 Camera and Photographic Supply Stores
    0.0052,  # 5947 Gift, Card, Novelty, and Souvenir Shops
    0.0052,  # 5948 Luggage and Leather Goods Stores
    0.0052,  # 5949 Fabric Stores, Piece Goods, and Sewing Notions
    0.0052,  # 5600 Apparel and Accessory Services (Cleaning, Alterations, etc.)
    # Home & Hardware – 0.52%
    0.0052,  # 5211 Lumber and Building Materials Stores, Hardware
    0.0052,  # 5251 Hardware Stores
    0.0052,  # 5261 Lawn and Garden Supply Stores
    0.0052,  # 5712 Furniture, Home Furnishings, and Equipment Stores
    0.0052,  # 5722 Household Appliance Stores
    0.0066,  # 5734 Computer Software Stores (Software & SaaS – 0.66%)
    0.0056,  # 5735 Record Stores, Video Tapes, and Disks (Media & Entertainment – 0.56%)
    0.0052,  # 5970 Artist Supply and Craft Shops
    # Health & Beauty Services – 0.86%
    0.0086,  # 5912 Drug Stores and Pharmacies
    0.0060,  # 5971 Electrical and Electronic Repair Shops
    0.0052,  # 5972 Stamp and Coin Stores
    0.0086,  # 5975 Hearing Aids—Sales and Service
    0.0052,  # 5977 Cosmetic Stores
    0.0052,  # 5978 Typewriter Stores—Sales, Service, and Supplies
    0.0052,  # 5913 Packaged Liquor Stores
    0.0052,  # 5973 Antiquarian & Specialty Collectible Stores
    0.0066,  # 5974 Computer Network/Information Services (Digital Services – 0.66%)
    # Transportation & Travel – 0.89%
    0.0089,  # 4111 Local/Suburban Commuter Passenger Transport (Including Ferries)
    0.0089,  # 4121 Taxicabs and Limousines
    0.0089,  # 4131 Bus Lines, Motor Bus Lines, and Charters
    0.0089,  # 4411 Cruise Lines
    0.0089,  # 4457 Boat Rentals and Leases
    0.0089,  # 4468 Marinas, Marine Service and Supplies
    0.0089,  # 4511 Airlines, Air Carriers
    0.0089,  # 4784 Tolls and Bridge Fees
    0.0052,  # 4812 Telecommunication Equipment and Telephone Sales (Retail)
    0.0089,  # 4789 Transportation Services (Not Elsewhere Classified)
    0.0089,  # 7512 Automobile Rental Agencies
    0.0089,  # 7513 Automobile Parking Lots and Garages
    0.0089,  # 7519 Motor Home Rental
    # Lodging & Entertainment
    0.0012,  # 5811 Caterers (Restaurants – 0.12%)
    0.0089,  # 7011 Hotels, Motels, Resorts (Travel – 0.89%)
    0.0089,  # 7022 Sporting and Recreational Camps
    0.0056,  # 7032 Amusement Parks (Entertainment – 0.56%)
    0.0089,  # 7033 Campgrounds and Trailer Parks
    0.0060,  # 7210 Laundry, Cleaning, and Garment Services
    0.0060,  # 7211 Laundry Services
    0.0060,  # 7216 Dry Cleaners
    0.0086,  # 7230 Beauty and Barber Shops
    0.0086,  # 7297 Massage Parlors, Sauna and Steam Baths
    0.0086,  # 7298 Health and Beauty Spas
    0.0060,  # 7311 Advertising Services—Outdoor
    0.0055,  # 7321 Consumer Credit Reporting Agencies (Financial – 0.55%)
    0.0055,  # 7322 Debt Collection Agencies
    0.0060,  # 7338 Quick Copy, Reproduction, and Blueprinting Services
    0.0060,  # 7339 Stenographic and Secretarial Support Services
    0.0060,  # 7342 Disinfecting and Pest Control Services
    0.0060,  # 7349 Cleaning, Maintenance, and Janitorial Services
    0.0089,  # 7511 Truck Stop (Truck Parking, Services)
    # Gambling & Betting – 1.50%
    0.0150,  # 7995 Gambling—Casinos, Race Tracks
    # Professional & Business Services
    0.0086,  # 8011 Medical and Dental Laboratories
    0.0086,  # 8021 Offices and Clinics of Dentists
    0.0086,  # 8031 Offices and Clinics of Doctors of Medicine
    0.0086,  # 8041 Offices and Clinics of Chiropractors
    0.0086,  # 8042 Offices and Clinics of Optometrists
    0.0086,  # 8043 Offices and Clinics of Osteopaths
    0.0086,  # 8049 Offices and Clinics of Health Practitioners, Not Elsewhere Classified
    0.0086,  # 8050 Nursing and Personal Care Facilities
    0.0086,  # 8062 Hospitals
    0.0086,  # 8099 Health and Allied Services, Not Elsewhere Classified
    0.0060,  # 8111 Legal Services and Attorneys
    # Education & Training – 1.02%
    0.0102,  # 8211 Elementary and Secondary Schools
    0.0102,  # 8220 Colleges, Universities, Professional Schools
    0.0102,  # 8241 Correspondence Schools
    0.0102,  # 8244 Business and Secretarial Schools
    0.0102,  # 8249 Vocational and Trade Schools
    0.0102,  # 8299 Schools and Educational Services (Not Elsewhere Classified)
    # Non-profit & Government – default average 0.60%
    0.0060,  # 8398 Charitable and Social Service Organizations
    0.0060,  # 8661 Religious Organizations
    0.0060,  # 9211 Court Costs, Including Alimony and Child Support
    0.0060,  # 9222 Fines
    0.0060,  # 9311 Tax Payments
    0.0060,  # 9399 Government Services (Not Elsewhere Classified)
    0.0060,  # 9402 Postal Services—Government Only
]
