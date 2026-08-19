# 🐉 Vassal of Tiamat - Dynamic Management System

Botun **HER BİR ÖZELLİĞİ** kodlarla oynamanıza gerek kalmadan, doğrudan Discord içerisinden Slash komutlarıyla canlı olarak değiştirilebilir, eklenebilir veya silinebilir hale getirildi. Tüm değişiklikler `bot_data.json` dosyasında saklanır ve bot kapansa bile kaybolmaz!

---

## 🛠️ Discord İçi Canlı Yönetim Komutları Listesi

### 👋 1. Karşılama ve Uğurlama Ayarları
- **`/karsilama_kanali_yap`** ➔ Bulunduğunuz kanalı otomatik olarak Hoşgeldin / Görüşürüz kanalı yapar.
- **`/karsilama_mesaji_ayarla mesaj:`** ➔ Giriş mesajını değiştirir. *(Örn: `Aramıza hoşgeldin {user}! {server} sunucusuna katıldın.`)*
- **`/karsilama_gif_ayarla gif_url:`** ➔ Katılma anında gönderilecek GIF linkini değiştirir.
- **`/ugurlama_mesaji_ayarla mesaj:`** ➔ Çıkış mesajını değiştirir.
- **`/ugurlama_gif_ayarla gif_url:`** ➔ Çıkış anında gönderilecek GIF linkini değiştirir.
- **`/karsilama_bilgisi`** ➔ Şu an aktif olan tüm karşılama/uğurlama mesajlarını ve GIF linklerini özetler.

---

### 🤖 2. Oto-Cevap ve GIF Yönetimi
- **`/otocevap_ekle tetikleyici: yanit: wildcard:`** 
  - Bota yeni mesaj yanıtı veya GIF ekler.
  - Aynı kelimeye birden fazla farklı yanıt eklerseniz, bot her seferinde **rastgele birini seçerek** cevap verir!
  - `wildcard: True` yaparsanız cümlenin içinde geçmesi yeterlidir.
- **`/otocevap_sil tetikleyici:`** ➔ Eklenmiş oto cevabı siler.
- **`/otocevap_listele`** ➔ Ekli tüm oto cevapları ve kaç farklı yanıt içerdiğini gösterir.

---

### 🎭 3. Dinamik Rol Menüleri ve Rol Oluşturma
- **`/ozel_rol_menusu baslik: aciklama: roller:`** 
  - İstediğiniz kanala kendi seçtiğiniz rollerden oluşan tıklamalı bir rol menüsü gönderir. *(Rolleri virgülle ayırarak yazabilirsiniz: `kırmızı, mavi, Oyun`)*
- **`/rol_olustur rol_adi:`** ➔ Sunucuda anında yeni bir Discord rolü oluşturur.
- **`/rolleri_olustur`** ➔ Menülerdeki 25 adet hazır rolü tek tıkla sunucuya ekler.
- **`/rol_menusu tur:ilgi | renk | muzik`** ➔ Ekran görüntülerinizdeki hazır menüleri kanala atar.

---

### 👑 4. Bot Durumu (Oynuyor/İzliyor)
- **`/durum_ayarla durum:`** ➔ Botun oynuyor/izliyor yazısını canlı olarak değiştirir. *(Örn: `Heavenly Court 🐉`)*

---

## ☁️ 7/24 Ücretsiz Yayınlama (Discloud)
1. Proje klasöründeki dosyaları (`bot.py`, `config.py`, `requirements.txt`, `.env`, `discloud.config`) zipleyin.
2. `.env` içine `DISCORD_TOKEN` ve varsa `JSONBIN_API_KEY` / `JSONBIN_BIN_ID` değerlerini yazın.
3. [discloud.app](https://discloud.app/) paneline yükleyin.
4. Botunuz 7/24 kesintisiz çalışacaktır!
