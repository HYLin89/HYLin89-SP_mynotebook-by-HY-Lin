簡易專案-內容導向之筆記 API ver 1.0
===
# 專案簡介
 
此專案為「內容創作與社群交流平台」的專屬後端服務，基於 Python Flask 框架與 RESTful 架構開發。負責處理前端的所有業務邏輯，包含嚴密的會員身分驗證、Markdown 文章的資料持久化、即時站內信通訊，以及與 Supabase 整合的雲端資源管理。

## 核心功能

* **會員與驗證系統 (Authentication & Authorization)**
  * 完整的註冊、登入、登出與信箱驗證流程。
  * 基於 PyJWT 的雙向安全驗證，並實作 **JTI 黑名單機制** 防範惡意存取。
  * 個人品牌資訊管理（自訂頭像、第三方連結）。
* **內容管理系統 (Content Management)**
  * 支援文章（筆記）的 CRUD 操作，區分草稿與發布狀態。
  * 書籤（收藏）功能與文章標籤（Tags）分類。
  * 整合 Supabase Storage Bucket 處理封面圖片的上傳與管理。
* **即時通訊系統 (Real-time Messaging)**
  * 採用 Flask-SocketIO 支援即時站內信推播。
  * 結構化的信件緒（Thread）資料庫設計，支援高效的「整串已讀」與「最新回覆」查詢。
* **自動化排程與效能優化 (Background Jobs)**
  * 獨立清理 API 設計，配合外部 cron-job.org 定期清除資料庫中過期的 Token 與黑名單，維持資料庫輕量與查詢效能。


# 核心技術

* **核心架構**： Python 3.10+, Flask, Flask-Restful
* **即時通訊**： Flask-socketio
* **資料庫及ORM**： PostgreSQL (使用supabase), Flask-SQLAlchemy
* **身分驗證與安全**： PyJWT, Werkzeug(password-hash), Flask-Cors, Flask-Limiter 
* **雲端與第三方服務**：
  * **信箱寄送**：Flask-Mail
  * **靜態檔案儲存**：Supabase Storage Bucket
  * **背景排程**：cron-job.org 
* **部署與託管**： Render
* **伺服器**: Gunicorn, Eventlet

# 目錄
```
├── main.py / server.py     # 應用程式入口與伺服器設定  
├── model.py                # SQLAlchemy 資料庫模型定義   (Models)  
├── pyproject.toml / uv.lock # 專案依賴管理  
├── resources/              # RESTful API 路由與控制器  
│   ├── accounts.py         # 帳號與驗證相關  
│   ├── articles.py         # 文章 CRUD  
│   ├── bookmark.py         # 書籤收藏功能  
│   ├── messages.py         # 站內信箱與即時訊息  
│   └── tknmanage.py        # Token 黑名單與排程清理  
├── util/                   # 共用輔助工具  
│   ├── auth.py             # JWT 驗證與裝飾器  
│   ├── mail.py             # 電子郵件發送邏輯  
│   ├── storage.py          # Supabase Bucket 上傳/刪除邏輯  
│   └── tags.py             # 標籤解析與處理  
└── README.md               # 專案說明文件  
```

# 使用範例
#### Request Examples
    1. 登入   
        [POST] /api/v1/login 
        Body
        {
            'account_login':'foo',
            'psw_login':'FooBar#123'
        } 

        Response - 200
        {
            'msg':'success',
            'user_data':{
                'account':'foo',
                'email':'foobar@****.***',
                'user_name':'foobar987'
            },
            'valid_token':'eyJhbGciOiJIUzI1NiIs...'
        }


***
    2.發布文章
        # Endpoint : [POST] /api/v1/article
        # Headers : 
        {
            'Authorization':'Bearer eyJhbGciOiJIUzI1NiIs...'
        }
        # Body :
        {
            'title':'結構動力學ch1',
            'cover_img':'https://.../supabase/...',
            'content':'## 自由震動<br>....',
            'status':'draft'
        }  
        # Body :
        (200 OK)
        {
            'msg':'success'
        }

# 配置要求
Python版本 3.10+  
* flask 
* flask-cors
* flask-limiter
* flask-mail
* flask-restful
* flask-socketio
* flask-sqlalchemy
* pyjwt
* psycopg2
* supabase
* werkzeug  
### 環境變數與說明  
* JWT_SECRET_KEY: 用於PyJWT解編碼使用之密鑰
* PROJECT_BUCKET_URL: supabase bucket連線使用之位置
* SERVICE_ROLE_KEY: 操作及連線supabse bucket用之密鑰
* PROJECT_PGSQL_URL: supabase 連線使用之位置
* MAIL_ADDR: 寄發信件之信箱地址
* MAIL_PSW: 寄發信件之信箱密碼
* ALLOW_FE_URL: 前端目的地位置
* DEFAULT_COVER_URL: 文章預設封面位置
* **CRON_AUTH_SECRETS**: **排程設定密鑰**

## 部署相關注意事項

本專案配置為可直接部署至雲端平台（如 Render）。

### 正式環境啟動指令 (Start Command)
為了確保 Flask-SocketIO 的即時通訊功能在生產環境中正常運作，**請勿**使用 Flask 內建的開發伺服器啟動。請在雲端平台的啟動指令設定如下：

```bash
gunicorn -b 0.0.0.0:$PORT -w 1 --threads 100 --timeout 60 main:app   
```
# 架構設計 
## 背景排程 (參見 tknmanage.py)
為了兼顧 JWT 的無狀態性與系統安全性，本專案實作了混合式的 Token 管理機制：

1. **JTI 黑名單**：使用者登出時，將 Token 的唯一識別碼 (JTI) 寫入資料庫黑名單，立即阻斷該 Token 的後續存取。

2. **自動化清理**：為避免黑名單資料庫無限制膨脹，專案內設計了一支專屬的清理 API (tknmanage.py)。透過設定 cron-job.org 攜帶專屬的**CRON_ AUTH_ SECRETS** 標頭，系統會定時觸發該 API，自動抹除資料庫中已超過原始有效期限的廢棄 Token 紀錄，維持資料庫最佳效能。

## 圖片處理 (參見 storage.py)
為了確保上傳至 Supabase Storage 的檔案安全性，並降低伺服器的記憶體負載與不必要的雲端 API 成本，本專案在圖片上傳路由中實作了輕量級的底層檢核機制：
  
1. **魔術數字檢查**：不依賴容易被偽造的副檔名或前端傳遞的 MIME Type。系統會直接讀取 Form-Data 二進制資料的表頭特徵碼 (Header Signature)，精準識別並攔截不合法的檔案格式，大幅提升防禦惡意檔案上傳的安全性。  

2. **記憶體友善的容量檢查**：放棄將整個檔案載入記憶體中計算大小的傳統做法，改採 Python 內建的檔案指針操作。透過 `file.seek(0, 2)` 以及 `file.tell()` 瞬間取得真實檔案位元組大小。   

透過以上機制，避免讀取超大惡意檔案導致伺服器OOM，在連線前先行攔截減少不必要的消耗與storage寫入失敗風險，並且迅速完成處理，給與用戶即時的錯誤反饋。


