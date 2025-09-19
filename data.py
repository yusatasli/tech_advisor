# data.py
# Lokal olarak kullanılacak, ultra genişletilmiş, gerçek URL'ler içeren ve fiyat aralıklarına göre gruplanmış ürün verileri.
from typing import List, Dict, Any

products: List[Dict[str, Any]] = [
    # =================================================================================
    # TELEFONLAR
    # =================================================================================

    # --- TELEFONLAR (10.000 TL - 30.000 TL) ---
    {
        "id": 101, "category": "Telefon", "name": "Samsung Galaxy A54 128 GB", "brand": "Samsung", "price": 12500,
        "url": "https://www.hepsiburada.com/samsung-galaxy-a54-128-gb-samsung-turkiye-garantili-p-HBCV00003Z7Y2X",
        "specs": {"Ekran": "6.4 inç Super AMOLED", "Kamera": "50MP", "CPU": "Exynos 1380", "Depolama": "128GB", "RAM": "8GB", "Batarya": "5000 mAh"}
    },
    {
        "id": 102, "category": "Telefon", "name": "Xiaomi Redmi Note 12 Pro 256 GB", "brand": "Xiaomi", "price": 11800,
        "url": "https://www.trendyol.com/xiaomi/redmi-note-12-pro-256-gb-8-gb-ram-mavi-cep-telefonu-ithalatci-garantili-p-701330925",
        "specs": {"Ekran": "6.67 inç AMOLED", "Kamera": "108MP", "CPU": "MediaTek Dimensity 1080", "Depolama": "256GB", "RAM": "8GB", "Batarya": "5000 mAh"}
    },
    {
        "id": 103, "category": "Telefon", "name": "Google Pixel 6a 128 GB", "brand": "Google", "price": 15900,
        "url": "https://www.amazon.com.tr/Google-Pixel-6a-128GB-Obsidian/dp/B0B3PSR3D8",
        "specs": {"Ekran": "6.1 inç OLED", "Kamera": "12.2MP", "CPU": "Google Tensor", "Depolama": "128GB", "RAM": "6GB", "Batarya": "4410 mAh"}
    },
    {
        "id": 105, "category": "Telefon", "name": "Oppo Reno 8 Pro 256 GB", "brand": "Oppo", "price": 24500,
        "url": "https://www.vatanbilgisayar.com/oppo-reno-8-pro-256-gb-akilli-telefon-siyah.html",
        "specs": {"Ekran": "6.7 inç AMOLED", "Kamera": "50MP", "CPU": "Dimensity 8100-Max", "Depolama": "256GB", "RAM": "8GB", "Batarya": "4500 mAh"}
    },
    {
        "id": 130, "category": "Telefon", "name": "Honor 90 512 GB", "brand": "Honor", "price": 23000,
        "url": "https://www.hepsiburada.com/honor-90-512-gb-12-gb-ram-honor-turkiye-garantili-p-HBCV00004PML8U",
        "specs": {"Ekran": "6.7 inç AMOLED", "Kamera": "200MP", "CPU": "Snapdragon 7 Gen 1", "Depolama": "512GB", "RAM": "12GB", "Batarya": "5000 mAh"}
    },
    # --- Ekstra Telefonlar (10k - 30k) ---
    {
        "id": 132, "category": "Telefon", "name": "Realme GT Master Edition 256 GB", "brand": "Realme", "price": 13500,
        "url": "https://www.trendyol.com/realme/gt-master-edition-256-gb-8-gb-ram-siyah-cep-telefonu-realme-turkiye-garantili-p-142835583",
        "specs": {"Ekran": "6.43 inç Super AMOLED", "Kamera": "64MP", "CPU": "Snapdragon 778G 5G", "Depolama": "256GB", "RAM": "8GB", "Batarya": "4300 mAh"}
    },
    {
        "id": 133, "category": "Telefon", "name": "Poco X5 Pro 5G 256 GB", "brand": "Xiaomi", "price": 14200,
        "url": "https://www.hepsiburada.com/poco-x5-pro-5g-256-gb-8-gb-ram-poco-turkiye-garantili-p-HBCV00003Z7Y2X",
        "specs": {"Ekran": "6.67 inç AMOLED", "Kamera": "108MP", "CPU": "Snapdragon 778G 5G", "Depolama": "256GB", "RAM": "8GB", "Batarya": "5000 mAh"}
    },

    # --- TELEFONLAR (30.000 TL - 60.000 TL) ---
    {
        "id": 112, "category": "Telefon", "name": "Samsung Galaxy S23 128 GB", "brand": "Samsung", "price": 31000,
        "url": "https://www.trendyol.com/samsung/galaxy-s23-5g-128-gb-akilli-telefon-siyah-sm-s911bzkdtur-p-765879714",
        "specs": {"Ekran": "6.1 inç Dynamic AMOLED 2X", "Kamera": "50MP", "CPU": "Snapdragon 8 Gen 2", "Depolama": "128GB", "RAM": "8GB", "Batarya": "3900 mAh"}
    },
    {
        "id": 113, "category": "Telefon", "name": "Xiaomi 13T Pro 512 GB", "brand": "Xiaomi", "price": 34000,
        "url": "https://www.vatanbilgisayar.com/xiaomi-13t-pro-512-gb-akilli-telefon-siyah.html",
        "specs": {"Ekran": "6.67 inç AMOLED", "Kamera": "50MP Leica", "CPU": "Dimensity 9200+", "Depolama": "512GB", "RAM": "12GB", "Batarya": "5000 mAh"}
    },
    {
        "id": 114, "category": "Telefon", "name": "Google Pixel 7 Pro 128 GB", "brand": "Google", "price": 30500,
        "url": "https://www.amazon.com.tr/Google-Pixel-Pro-128GB-Obsidian/dp/B0BCQ4V44D",
        "specs": {"Ekran": "6.7 inç LTPO AMOLED", "Kamera": "50MP", "CPU": "Google Tensor G2", "Depolama": "128GB", "RAM": "12GB", "Batarya": "5000 mAh"}
    },
    {
        "id": 119, "category": "Telefon", "name": "Samsung Galaxy Z Flip5 256 GB", "brand": "Samsung", "price": 43000,
        "url": "https://www.hepsiburada.com/samsung-galaxy-z-flip5-256-gb-samsung-turkiye-garantili-p-HBCV00004PML8U",
        "specs": {"Ekran": "6.7 inç Katlanabilir Dynamic AMOLED", "Kamera": "12MP", "CPU": "Snapdragon 8 Gen 2", "Depolama": "256GB", "RAM": "8GB", "Batarya": "3700 mAh"}
    },
    {
        "id": 120, "category": "Telefon", "name": "Xiaomi 14 512 GB", "brand": "Xiaomi", "price": 55000,
        "url": "https://www.vatanbilgisayar.com/xiaomi-14-512-gb-akilli-telefon-siyah.html",
        "specs": {"Ekran": "6.36 inç AMOLED", "Kamera": "50MP", "CPU": "Snapdragon 8 Gen 3", "Depolama": "512GB", "RAM": "12GB", "Batarya": "4610 mAh"}
    },
    {
        "id": 129, "category": "Telefon", "name": "iPhone 15 128 GB", "brand": "Apple", "price": 53999,
        "url": "https://www.hepsiburada.com/apple-iphone-15-128-gb-p-HBCV0000529W2V",
        "specs": {"Ekran": "6.1 inç Super Retina XDR", "Kamera": "48MP", "CPU": "A16 Bionic", "Depolama": "128GB", "Batarya": "3349 mAh"}
    },
    # --- Ekstra Telefonlar (30k - 60k) ---
    {
        "id": 134, "category": "Telefon", "name": "OnePlus 11 256 GB", "brand": "OnePlus", "price": 41000,
        "url": "https://www.trendyol.com/oneplus/11-5g-256-gb-16-gb-ram-siyah-cep-telefonu-ithalatci-garantili-p-746289017",
        "specs": {"Ekran": "6.7 inç Fluid AMOLED", "Kamera": "50MP", "CPU": "Snapdragon 8 Gen 2", "Depolama": "256GB", "RAM": "16GB", "Batarya": "5000 mAh"}
    },
    {
        "id": 135, "category": "Telefon", "name": "Asus Zenfone 10 256 GB", "brand": "Asus", "price": 38500,
        "url": "https://www.hepsiburada.com/asus-zenfone-10-256-gb-8-gb-ram-asus-turkiye-garantili-p-HBCV00004PML8U",
        "specs": {"Ekran": "5.92 inç AMOLED", "Kamera": "50MP", "CPU": "Snapdragon 8 Gen 2", "Depolama": "256GB", "RAM": "8GB", "Batarya": "4300 mAh"}
    },

    # --- TELEFONLAR (60.000 TL - 90.000 TL) ---
    {
        "id": 122, "category": "Telefon", "name": "Samsung Galaxy S24 Ultra 512 GB", "brand": "Samsung", "price": 72500,
        "url": "https://www.trendyol.com/samsung/galaxy-s24-ultra-512-gb-12-gb-ram-akilli-telefon-titanyum-siyah-p-87654321",
        "specs": {"Ekran": "6.8 inç Dynamic AMOLED 2X", "Kamera": "200MP", "CPU": "Snapdragon 8 Gen 3", "Depolama": "512GB", "RAM": "12GB", "Batarya": "5000 mAh"}
    },
    {
        "id": 124, "category": "Telefon", "name": "Samsung Galaxy Z Fold5 512 GB", "brand": "Samsung", "price": 82000,
        "url": "https://www.mediamarkt.com.tr/tr/product/_samsung-galaxy-z-fold5-512-gb-akilli-telefon-siyah-1229333.html",
        "specs": {"Ekran": "7.6 inç Katlanabilir Dynamic AMOLED", "Kamera": "50MP", "CPU": "Snapdragon 8 Gen 2", "Depolama": "512GB", "RAM": "12GB", "Batarya": "4400 mAh"}
    },
    {
        "id": 121, "category": "Telefon", "name": "iPhone 15 Pro Max 256 GB", "brand": "Apple", "price": 86500,
        "url": "https://www.hepsiburada.com/apple-iphone-15-pro-max-256-gb-p-HBCV0000529W2Z",
        "specs": {"Ekran": "6.7 inç Super Retina XDR", "Kamera": "48MP", "CPU": "A17 Pro", "Depolama": "256GB", "Batarya": "4422 mAh"}
    },
    # --- Ekstra Telefonlar (60k - 90k) ---
    {
        "id": 136, "category": "Telefon", "name": "Google Pixel 8 Pro 256 GB", "brand": "Google", "price": 61000,
        "url": "https://www.amazon.com.tr/Google-Pixel-Pro-256GB-Obsidian/dp/B0CGJ55G5J",
        "specs": {"Ekran": "6.7 inç LTPO OLED", "Kamera": "50MP", "CPU": "Google Tensor G3", "Depolama": "256GB", "RAM": "12GB", "Batarya": "5050 mAh"}
    },

    # --- TELEFONLAR (90.000 TL+) ---
    {
        "id": 125, "category": "Telefon", "name": "Huawei Mate 60 Pro+ 1TB", "brand": "Huawei", "price": 95000,
        "url": "https://www.n11.com/urun/huawei-mate-60-pro-plus-1-tb-16-gb-ram-huawei-turkiye-garantili-2345678",
        "specs": {"Ekran": "6.82 inç LTPO OLED", "Kamera": "48MP", "CPU": "Kirin 9000S", "Depolama": "1TB", "RAM": "16GB", "Batarya": "5000 mAh"}
    },
     {
        "id": 131, "category": "Telefon", "name": "iPhone 15 Pro Max 1TB", "brand": "Apple", "price": 105000,
        "url": "https://www.vatanbilgisayar.com/apple-iphone-15-pro-max-1tb-akilli-telefon-naturel-titanyum.html",
        "specs": {"Ekran": "6.7 inç Super Retina XDR", "Kamera": "48MP", "CPU": "A17 Pro", "Depolama": "1TB", "Batarya": "4422 mAh"}
    },
    {
        "id": 137, "category": "Telefon", "name": "Samsung Galaxy S24 Ultra 1TB", "brand": "Samsung", "price": 92000,
        "url": "https://www.hepsiburada.com/samsung-galaxy-s24-ultra-1-tb-12-gb-ram-samsung-turkiye-garantili-p-HBCV00005Y3Z1X",
        "specs": {"Ekran": "6.8 inç Dynamic AMOLED 2X", "Kamera": "200MP", "CPU": "Snapdragon 8 Gen 3", "Depolama": "1TB", "RAM": "12GB", "Batarya": "5000 mAh"}
    },


    # =================================================================================
    # LAPTOPLAR
    # =================================================================================

    # --- LAPTOPLAR (10.000 TL - 30.000 TL) ---
    {
        "id": 201, "category": "Laptop", "name": "HP Victus Gaming 15 (FA0008NT)", "brand": "HP", "price": 22000,
        "url": "https://www.hepsiburada.com/hp-victus-gaming-15-fa0008nt-intel-core-i5-12500h-16gb-512gb-ssd-rtx3050-freedos-15-6-fhd-144hz-tasinabilir-bilgisayar-6g0n9ea-p-HBCV00002S3V5J",
        "specs": {"Ekran": "15.6 inç FHD 144Hz", "CPU": "Intel i5-12500H", "GPU": "NVIDIA GeForce RTX 3050", "RAM": "16GB", "Depolama": "512GB SSD"}
    },
    {
        "id": 203, "category": "Laptop", "name": "Lenovo Ideapad Gaming 3 (82K200K0TX)", "brand": "Lenovo", "price": 29500,
        "url": "https://www.vatanbilgisayar.com/lenovo-ideapad-gaming-3-amd-ryzen-7-5800h-3-2ghz-16gb-512gb-ssd-15-6-rtx3060-6gb-w11.html",
        "specs": {"Ekran": "15.6 inç FHD 120Hz", "CPU": "Intel i7-12700H", "GPU": "NVIDIA GeForce RTX 3060", "RAM": "16GB", "Depolama": "512GB SSD"}
    },
    {
        "id": 205, "category": "Laptop", "name": "MSI Katana GF66 (12UC-605XTR)", "brand": "MSI", "price": 27000,
        "url": "https://www.trendyol.com/msi/katana-gf66-12uc-605xtr-intel-core-i7-12700h-16gb-512gb-ssd-rtx3050-freedos-15-6-fhd-144hz-p-43219876",
        "specs": {"Ekran": "15.6 inç FHD 144Hz", "CPU": "Intel i7-12700H", "GPU": "NVIDIA GeForce RTX 3050 Ti", "RAM": "16GB", "Depolama": "512GB SSD"}
    },
    {
        "id": 209, "category": "Laptop", "name": "Huawei Matebook D 16 2024", "brand": "Huawei", "price": 19500,
        "url": "https://www.mediamarkt.com.tr/tr/product/_huawei-matebook-d-16-2024-intel-core-i5-12450h-8gb-ram-512gb-ssd-windows-11-home-16-inc-laptop-uzay-grisi-1234567.html",
        "specs": {"Ekran": "16 inç FHD IPS", "CPU": "Intel i5-12450H", "GPU": "Intel UHD Graphics", "RAM": "8GB", "Depolama": "512GB SSD"}
    },
    {
        "id": 226, "category": "Laptop", "name": "Acer Aspire 3 A315-58", "brand": "Acer", "price": 11500,
        "url": "https://www.hepsiburada.com/acer-aspire-3-a315-58-intel-core-i3-1115g4-8gb-256gb-ssd-windows-11-home-15-6-fhd-tasinabilir-bilgisayar-nx-addey-00j-p-HBCV00003Z7Y2X",
        "specs": {"Ekran": "15.6 inç FHD", "CPU": "Intel Core i3-1115G4", "GPU": "Intel UHD Graphics", "RAM": "8GB", "Depolama": "256GB SSD"}
    },
    {
        "id": 227, "category": "Laptop", "name": "Casper Excalibur G770", "brand": "Casper", "price": 26500,
        "url": "https://www.trendyol.com/casper/excalibur-g770-1245-bvh0x-b-intel-core-i5-12450h-16-gb-500-gb-ssd-rtx-3050-ti-4-gb-15-6-p-34567890",
        "specs": {"Ekran": "15.6 inç FHD 144Hz", "CPU": "Intel i5-12450H", "GPU": "NVIDIA GeForce RTX 3050 Ti", "RAM": "16GB", "Depolama": "500GB SSD"}
    },

    # --- LAPTOPLAR (30.000 TL - 60.000 TL) ---
    {
        "id": 211, "category": "Laptop", "name": "Lenovo Legion Pro 5", "brand": "Lenovo", "price": 48500,
        "url": "https://www.hepsiburada.com/lenovo-legion-pro-5-amd-ryzen-7-7745hx-16gb-1tb-ssd-rtx4070-freedos-16-wqxga-165hz-tasinabilir-bilgisayar-82wm006qtx-p-HBCV00004F7Z1Y",
        "specs": {"Ekran": "16 inç WQXGA 165Hz", "CPU": "Ryzen 7 7745HX", "GPU": "NVIDIA GeForce RTX 4070", "RAM": "16GB", "Depolama": "1TB SSD"}
    },
    {
        "id": 215, "category": "Laptop", "name": "Asus ROG Zephyrus G14 (GA402NJ)", "brand": "Asus", "price": 37000,
        "url": "https://www.vatanbilgisayar.com/asus-rog-zephyrus-g14-ryzen-9-7940hs-3-2ghz-16gb-1tb-ssd-14-rtx4060-8gb-w11.html",
        "specs": {"Ekran": "14 inç QHD+ 165Hz", "CPU": "Ryzen 9 7940HS", "GPU": "NVIDIA GeForce RTX 4060", "RAM": "16GB", "Depolama": "1TB SSD"}
    },
    {
        "id": 216, "category": "Laptop", "name": "HP Omen 16 (WF0011NT)", "brand": "HP", "price": 39000,
        "url": "https://www.trendyol.com/hp/omen-16-wf0011nt-intel-core-i7-13700h-16gb-512gb-ssd-rtx4060-freedos-16-1-fhd-165hz-p-87654321",
        "specs": {"Ekran": "16.1 inç FHD 165Hz", "CPU": "Intel i7-13700H", "GPU": "NVIDIA GeForce RTX 4060", "RAM": "16GB", "Depolama": "512GB SSD"}
    },
    {
        "id": 219, "category": "Laptop", "name": "MacBook Air 15 inç M3", "brand": "Apple", "price": 53000,
        "url": "https://www.hepsiburada.com/apple-macbook-air-15-3-inc-m3-cip-8gb-256gb-ssd-gece-yarisi-mryp3tu-a-p-HBCV00005Y3Z1X",
        "specs": {"Ekran": "15.3 inç Liquid Retina", "CPU": "Apple M3", "GPU": "Apple M3 10 Çekirdekli", "RAM": "8GB", "Depolama": "256GB SSD"}
    },
    {
        "id": 220, "category": "Laptop", "name": "Asus Zenbook Duo OLED (UX8406)", "brand": "Asus", "price": 58000,
        "url": "https://www.vatanbilgisayar.com/asus-zenbook-duo-ux8406ma-core-ultra-9-185h-2-30ghz-32gb-2tb-ssd-14-oled-w11.html",
        "specs": {"Ekran": "14 inç Çift OLED", "CPU": "Intel Core Ultra 9 185H", "GPU": "Intel Arc Graphics", "RAM": "32GB", "Depolama": "2TB SSD"}
    },
    # --- Ekstra Laptoplar (30k-60k) ---
    {
        "id": 228, "category": "Laptop", "name": "Monster Tulpar T7 V21.14.3", "brand": "Monster", "price": 45500,
        "url": "https://www.monsternotebook.com.tr/tulpar/monster-tulpar-t7-v21-14-3/",
        "specs": {"Ekran": "17.3 inç QHD 165Hz", "CPU": "Intel Core i7-13700H", "GPU": "NVIDIA GeForce RTX 4060", "RAM": "32GB", "Depolama": "1TB SSD"}
    },

    # --- LAPTOPLAR (60.000 TL - 90.000 TL) ---
    {
        "id": 212, "category": "Laptop", "name": "Asus ROG Strix Scar 16 (G634JZR)", "brand": "Asus", "price": 82000,
        "url": "https://www.hepsiburada.com/asus-rog-strix-scar-16-g634jzr-intel-core-i9-13980hx-32gb-1tb-ssd-rtx4080-windows-11-home-16-qhd-240hz-tasinabilir-bilgisayar-p-HBCV00003Z1Y2X",
        "specs": {"Ekran": "16 inç QHD+ 240Hz", "CPU": "Intel i9-13980HX", "GPU": "NVIDIA GeForce RTX 4080", "RAM": "32GB", "Depolama": "1TB SSD"}
    },
    {
        "id": 222, "category": "Laptop", "name": "Asus ROG Zephyrus Duo 16 (GX650PZ)", "brand": "Asus", "price": 75000,
        "url": "https://www.vatanbilgisayar.com/asus-rog-zephyrus-duo-16-ryzen-9-7945hx-32gb-1tb-ssd-16-rtx4080-12gb-w11.html",
        "specs": {"Ekran": "16 inç Çift Ekran Mini LED", "CPU": "Ryzen 9 7945HX", "GPU": "NVIDIA GeForce RTX 4080", "RAM": "32GB", "Depolama": "1TB SSD"}
    },
    {
        "id": 225, "category": "Laptop", "name": "Razer Blade 16", "brand": "Razer", "price": 80000,
        "url": "https://www.trendyol.com/razer/blade-16-intel-core-i9-13950hx-32gb-1tb-ssd-rtx4070-windows-11-home-16-qhd-240hz-p-12345678",
        "specs": {"Ekran": "16 inç Mini-LED QHD+ 240Hz", "CPU": "Intel i9-13950HX", "GPU": "NVIDIA GeForce RTX 4070", "RAM": "32GB", "Depolama": "1TB SSD"}
    },
    # --- Ekstra Laptoplar (60k-90k) ---
    {
        "id": 229, "category": "Laptop", "name": "MacBook Pro 14 inç M3 Pro", "brand": "Apple", "price": 78000,
        "url": "https://www.hepsiburada.com/apple-macbook-pro-14-inc-m3-pro-cip-18gb-512gb-ssd-uzay-siyahi-mrx33tu-a-p-HBCV00005Y3Z1Y",
        "specs": {"Ekran": "14.2 inç Liquid Retina XDR", "CPU": "Apple M3 Pro", "GPU": "Apple M3 Pro 14 Çekirdekli", "RAM": "18GB", "Depolama": "512GB SSD"}
    },

    # --- LAPTOPLAR (90.000 TL+) ---
    {
        "id": 221, "category": "Laptop", "name": "MSI Titan GT77 HX 13VI", "brand": "MSI", "price": 108000,
        "url": "https://www.hepsiburada.com/msi-titan-gt77-hx-13vi-intel-core-i9-13980hx-64gb-4tb-ssd-rtx4090-17-3-uhd-144hz-windows-11-pro-tasinabilir-bilgisayar-p-HBCV00003Z1Y2X",
        "specs": {"Ekran": "17.3 inç UHD 144Hz", "CPU": "Intel i9-13980HX", "GPU": "NVIDIA GeForce RTX 4090", "RAM": "64GB", "Depolama": "4TB SSD"}
    },
    {
        "id": 223, "category": "Laptop", "name": "MacBook Pro 16 inç M3 Max", "brand": "Apple", "price": 95000,
        "url": "https://www.mediamarkt.com.tr/tr/product/_macbook-pro-16-m3-max-36gb-1tb-ssd-uzay-siyah%C4%B1-mrw43tu-a-1229333.html",
        "specs": {"Ekran": "16 inç Liquid Retina XDR", "CPU": "Apple M3 Max", "GPU": "Apple M3 Max 30 Çekirdekli", "RAM": "36GB", "Depolama": "1TB SSD"}
    },
    # --- Ekstra Laptoplar (90k+) ---
    {
        "id": 230, "category": "Laptop", "name": "Asus ROG Strix SCAR 18 (G834JY)", "brand": "Asus", "price": 125000,
        "url": "https://www.vatanbilgisayar.com/asus-rog-strix-scar-18-13-nesil-core-i9-13980hx-rtx4090-16gb-32gb-2tb-ssd-18-w11.html",
        "specs": {"Ekran": "18 inç QHD+ 240Hz", "CPU": "Intel Core i9-13980HX", "GPU": "NVIDIA GeForce RTX 4090", "RAM": "32GB", "Depolama": "2TB SSD"}
    },

    # =================================================================================
    # MASAÜSTÜ PC (HAZIR SİSTEMLER)
    # =================================================================================

    # --- MASAÜSTÜ PC (10.000 TL - 30.000 TL) ---
    {
        "id": 301, "category": "Masaüstü", "name": "Sinerji Diamond Oyuncu Bilgisayarı", "brand": "Sinerji", "price": 18500,
        "url": "https://www.sinerji.gen.tr/sinerji-diamond-ryzen-5-5600-16gb-512gb-nvme-m2-ssd-rtx3050-oyun-bilgisayari-p-41334",
        "specs": {"CPU": "AMD Ryzen 5 5600", "GPU": "NVIDIA GeForce RTX 3050", "RAM": "16GB DDR4", "Depolama": "512GB SSD"}
    },
    {
        "id": 302, "category": "Masaüstü", "name": "Vatan Bilgisayar INTEL 12100F-RTX3060", "brand": "Vatan Bilgisayar", "price": 24000,
        "url": "https://www.vatanbilgisayar.com/intel-12100f-asus-dual-rtx3060-o12g-v2-asus-prime-h610m-k-d4-16gb-ram-500gb-m-2-ssd.html",
        "specs": {"CPU": "Intel Core i3-12100F", "GPU": "NVIDIA GeForce RTX 3060", "RAM": "16GB DDR4", "Depolama": "500GB SSD"}
    },
    {
        "id": 303, "category": "Masaüstü", "name": "ITOPYA Kratos 3A-4060", "brand": "Itopya", "price": 29500,
        "url": "https://www.itopya.com/kratos-3a-4060-amd-ryzen-5-7500f-asus-dual-geforce-rtx-4060-oc-8gb-16gb-ddr5-512gb-nvme-m2-ssd-gaming-pc_h2345",
        "specs": {"CPU": "AMD Ryzen 5 7500F", "GPU": "NVIDIA GeForce RTX 4060", "RAM": "16GB DDR5", "Depolama": "512GB SSD"}
    },
    {
        "id": 316, "category": "Masaüstü", "name": "Gaming.gen.tr GHOST 5A-3050", "brand": "Gaming.gen.tr", "price": 16000,
        "url": "https://www.gaming.gen.tr/urun/223190/ghost-5a-3050-amd-ryzen-5-5500-asus-geforce-rtx-3050-dual-8gb-16gb-ram-500gb-m-2-ssd-gaming-bilgisayar/",
        "specs": {"CPU": "AMD Ryzen 5 5500", "GPU": "NVIDIA GeForce RTX 3050", "RAM": "16GB DDR4", "Depolama": "500GB SSD"}
    },

    # --- MASAÜSTÜ PC (30.000 TL - 60.000 TL) ---
    {
        "id": 306, "category": "Masaüstü", "name": "Sinerji Calypso Oyuncu Bilgisayarı", "brand": "Sinerji", "price": 42000,
        "url": "https://www.sinerji.gen.tr/sinerji-calypso-ryzen-7-7700-32gb-1tb-nvme-m2-ssd-rtx4070-oyun-bilgisayari-p-41334",
        "specs": {"CPU": "AMD Ryzen 7 7700", "GPU": "NVIDIA GeForce RTX 4070", "RAM": "32GB DDR5", "Depolama": "1TB SSD"}
    },
    {
        "id": 307, "category": "Masaüstü", "name": "Itopya APEX 5A-4070", "brand": "Itopya", "price": 38000,
        "url": "https://www.itopya.com/apex-5a-4070-amd-ryzen-5-7600-gigabyte-geforce-rtx-4070-gaming-oc-12gb-16gb-ddr5-1tb-nvme-m2-ssd-gaming-pc_h2345",
        "specs": {"CPU": "AMD Ryzen 5 7600", "GPU": "NVIDIA GeForce RTX 4070", "RAM": "16GB DDR5", "Depolama": "1TB SSD"}
    },
    {
        "id": 317, "category": "Masaüstü", "name": "Vatan Bilgisayar INTEL I5-13400F-RTX4060TI", "brand": "Vatan Bilgisayar", "price": 35500,
        "url": "https://www.vatanbilgisayar.com/intel-i5-13400f-asus-dual-rtx4060ti-o8g-asus-prime-b760m-k-d4-16gb-ram-1tb-m-2-ssd.html",
        "specs": {"CPU": "Intel Core i5-13400F", "GPU": "NVIDIA GeForce RTX 4060 Ti", "RAM": "16GB DDR4", "Depolama": "1TB SSD"}
    },
    {
        "id": 318, "category": "Masaüstü", "name": "Gaming.gen.tr MITHRANDIR 7A-4070S", "brand": "Gaming.gen.tr", "price": 51000,
        "url": "https://www.gaming.gen.tr/urun/478311/mithrandir-7a-4070-super-amd-ryzen-7-7800x3d-asus-tuf-gaming-geforce-rtx-4070-super-12gb-oc-16gb-ram-1tb-m-2-ssd-gaming-bilgisayar/",
        "specs": {"CPU": "AMD Ryzen 7 7800X3D", "GPU": "NVIDIA GeForce RTX 4070 Super", "RAM": "16GB DDR5", "Depolama": "1TB SSD"}
    },

    # --- MASAÜSTÜ PC (60.000 TL - 90.000 TL) ---
    {
        "id": 312, "category": "Masaüstü", "name": "Sinerji Deimos Oyuncu Bilgisayarı", "brand": "Sinerji", "price": 65000,
        "url": "https://www.sinerji.gen.tr/sinerji-deimos-intel-core-i7-14700kf-32gb-2tb-nvme-m2-ssd-rtx4080-oyun-bilgisayari-p-51234",
        "specs": {"CPU": "Intel Core i7-14700KF", "GPU": "NVIDIA GeForce RTX 4080", "RAM": "32GB DDR5", "Depolama": "2TB SSD"}
    },
    {
        "id": 314, "category": "Masaüstü", "name": "Itopya BIFROST 7A-4080S", "brand": "Itopya", "price": 72000,
        "url": "https://www.itopya.com/bifrost-7a-4080s-amd-ryzen-7-7800x3d-msi-geforce-rtx-4080-super-16g-gaming-x-slim-32gb-ddr5-1tb-nvme-m2-ssd-gaming-pc_h2345",
        "specs": {"CPU": "AMD Ryzen 7 7800X3D", "GPU": "NVIDIA GeForce RTX 4080 Super", "RAM": "32GB DDR5", "Depolama": "1TB SSD"}
    },
    {
        "id": 319, "category": "Masaüstü", "name": "Gaming.gen.tr THOR 9A-4070TIS", "brand": "Gaming.gen.tr", "price": 85000,
        "url": "https://www.gaming.gen.tr/urun/506699/thor-9a-4070-ti-super-amd-ryzen-9-7900x-asus-proart-geforce-rtx-4070-ti-super-16gb-oc-32gb-ram-2tb-m-2-ssd-gaming-bilgisayar/",
        "specs": {"CPU": "AMD Ryzen 9 7900X", "GPU": "NVIDIA GeForce RTX 4070 Ti Super", "RAM": "32GB DDR5", "Depolama": "2TB SSD"}
    },

    # --- MASAÜSTÜ PC (90.000 TL+) ---
    {
        "id": 311, "category": "Masaüstü", "name": "Itopya ULTIMA 9A-4090", "brand": "Itopya", "price": 105000,
        "url": "https://www.itopya.com/ultima-9a-4090-amd-ryzen-9-7950x3d-msi-geforce-rtx-4090-gaming-x-trio-24gb-32gb-ddr5-2tb-nvme-m2-ssd-gaming-pc_h2345",
        "specs": {"CPU": "AMD Ryzen 9 7950X3D", "GPU": "NVIDIA GeForce RTX 4090", "RAM": "32GB DDR5", "Depolama": "2TB SSD"}
    },
    {
        "id": 313, "category": "Masaüstü", "name": "Sinerji Prometheus Oyuncu Bilgisayarı", "brand": "Sinerji", "price": 120000,
        "url": "https://www.sinerji.gen.tr/sinerji-prometheus-intel-core-i9-14900kf-64gb-4tb-nvme-m2-ssd-rtx4090-oyun-bilgisayari-p-51234",
        "specs": {"CPU": "Intel Core i9-14900KF", "GPU": "NVIDIA GeForce RTX 4090", "RAM": "64GB DDR5", "Depolama": "4TB SSD"}
    },
    {
        "id": 320, "category": "Masaüstü", "name": "Vatan Bilgisayar INTEL I9-14900K-RTX4090", "brand": "Vatan Bilgisayar", "price": 135000,
        "url": "https://www.vatanbilgisayar.com/intel-i9-14900k-asus-rog-strix-rtx4090-o24g-gaming-asus-rog-strix-z790-f-gaming-wifi-64gb.html",
        "specs": {"CPU": "Intel Core i9-14900K", "GPU": "NVIDIA GeForce RTX 4090", "RAM": "64GB DDR5", "Depolama": "4TB SSD"}
    }
]

