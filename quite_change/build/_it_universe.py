# -*- coding: utf-8 -*-
"""IT sector universe — 100 companies from TOPIX 情報・通信業.
Tiers: 30 Large / 30 Mid / 40 Small (by market cap within sector).

FY-end notes (for each company look up actual FY-end during research):
  Most use March 31 (FY3/20XX).
  Exceptions: Trend Micro, Nexon, Gungho, Rakuten, GMO internet group, Appier, Cybozu = Dec 31 (FY12)
              OBIC, Freee = June 30 (FY6); Sansan = May 31 (FY5); Hikari Tsushin = Aug 31 (FY8)
              Oracle Japan = May 31 (FY5); Anycolor = Apr 30 (FY4); GMO PG = Sep 30 (FY9)
              Smaregi = Oct 31 (FY10); CyberAgent = Sep 30 (FY9); Money Forward = Nov 30 (FY11)
              HEnNGE = Sep 30 (FY9); Visional = Jul 31 (FY7)
"""

# (ticker, name_en, name_jp, size)
IT_UNIVERSE = [
    # ── LARGE (30) ───────────────────────────────────────────────────
    ('9984', 'SoftBank Group',              'ソフトバンクグループ',          'large'),
    ('9432', 'NTT',                          '日本電信電話',                  'large'),
    ('9433', 'KDDI',                         'KDDI',                         'large'),
    ('9434', 'SoftBank Corp',                'ソフトバンク',                  'large'),
    ('4689', 'LY Corporation',               'LYコーポレーション',            'large'),
    ('9766', 'Konami Group',                 'コナミグループ',                 'large'),
    ('4307', 'Nomura Research Institute',    '野村総合研究所',                 'large'),
    ('4684', 'OBIC',                         'オービック',                    'large'),
    ('3659', 'Nexon',                        'ネクソン',                      'large'),
    ('9435', 'Hikari Tsushin',              '光通信',                         'large'),
    ('9697', 'Capcom',                       'カプコン',                      'large'),
    ('4716', 'Oracle Japan',                 'オラクル日本',                   'large'),
    ('9602', 'Toho',                         '東宝',                          'large'),
    ('4768', 'Otsuka Corp',                  '大塚商会',                      'large'),
    ('9412', 'SKY Perfect JSAT',             'スカパーJSAT',                  'large'),
    ('9401', 'TBS Holdings',                 'TBSホールディングス',            'large'),
    ('4676', 'Fuji Media Holdings',          'フジ・メディア・ホールディングス','large'),
    ('9684', 'Square Enix Holdings',         'スクウェア・エニックスHD',       'large'),
    ('4704', 'Trend Micro',                  'トレンドマイクロ',               'large'),
    ('3626', 'TIS',                          'TIS',                           'large'),
    ('9404', 'Nippon Television Holdings',   '日本テレビホールディングス',      'large'),
    ('9413', 'TV Tokyo Holdings',            'テレビ東京ホールディングス',      'large'),
    ('3769', 'GMO Payment Gateway',          'GMOペイメントゲートウェイ',       'large'),
    ('4385', 'Mercari',                      'メルカリ',                       'large'),
    ('2327', 'NS Solutions',                 'NS Solutions',                   'large'),
    ('3774', 'Internet Initiative Japan',    'インターネットイニシアティブ',    'large'),
    ('4816', 'Toei Animation',               '東映アニメーション',              'large'),
    ('9468', 'Kadokawa',                     'KADOKAWA',                       'large'),
    ('3635', 'Koei Tecmo Holdings',          'コーエーテクモHD',               'large'),
    ('9613', 'NTT Data Group',               'NTTデータグループ',              'large'),

    # ── MID (30) ─────────────────────────────────────────────────────
    ('8056', 'Biprogy',                      'ビプロジー',                     'mid'),
    ('4733', 'OBIC Business Consultants',    'オービックビジネスコンサルタント','mid'),
    ('9605', 'Toei',                         '東映',                           'mid'),
    ('4812', 'Dentsu Soken',                 '電通総研',                       'mid'),
    ('9409', 'TV Asahi Holdings',            'テレビ朝日ホールディングス',      'mid'),
    ('9436', 'Okinawa Cellular Telephone',   '沖縄セルラー電話',               'mid'),
    ('9449', 'GMO Internet Group',           'GMOインターネットグループ',       'mid'),
    ('3923', 'Rakus',                        'ラクス',                         'mid'),
    ('4194', 'Visional',                     'ビジョナル',                     'mid'),
    ('9418', 'U-NEXT Holdings',              'Uーネクストホールディングス',     'mid'),
    ('4686', 'JustSystems',                  'ジャストシステム',               'mid'),
    ('4373', 'Simplex Holdings',             'シンプレクス・ホールディングス',  'mid'),
    ('3994', 'Money Forward',               'マネーフォワード',               'mid'),
    ('9759', 'NSD',                          'NSD',                           'mid'),
    ('4443', 'Sansan',                       'Sansan',                         'mid'),
    ('9746', 'TKC',                          'TKC',                            'mid'),
    ('2317', 'Systena',                      'システナ',                       'mid'),
    ('4483', 'JMDC',                         'JMDC',                           'mid'),
    ('9682', 'DTS',                          'DTS',                            'mid'),
    ('4751', 'CyberAgent',                   'サイバーエージェント',            'mid'),
    ('5032', 'Anycolor',                     'エニーカラー',                   'mid'),
    ('4776', 'Cybozu',                       'サイボウズ',                     'mid'),
    ('4478', 'freee',                        'フリー',                         'mid'),
    ('4180', 'Appier Group',                 'アピエグループ',                 'mid'),
    ('3778', 'Sakura Internet',              'さくらインターネット',            'mid'),
    ('4475', 'HENNGE',                       'ヘンジ',                         'mid'),
    ('4431', 'Smaregi',                      'スマレジ',                       'mid'),
    ('9692', 'CEC',                          'CEC',                            'mid'),
    ('9715', 'Comture',                      'コムチュア',                     'mid'),
    ('2121', 'Mixi',                         'ミクシィ',                       'mid'),

    # ── SMALL (40) ───────────────────────────────────────────────────
    ('3765', 'GungHo Online Entertainment', 'ガンホー・オンライン・エンターテイメント', 'small'),
    ('4490', 'VisasQ',                       'ビザスク',                       'small'),
    ('4176', 'Coconala',                     'ココナラ',                       'small'),
    ('4165', 'Plaid',                        'プレイド',                       'small'),
    ('3914', 'JIG-SAW',                      'ジグソー',                       'small'),
    ('3853', 'Asteria',                      'アステリア',                     'small'),
    ('3915', 'TerraSky',                     'テラスカイ',                     'small'),
    ('4169', 'EneChange',                    'エネチェンジ',                   'small'),
    ('4264', 'Secure',                       'セキュア',                       'small'),
    ('4427', 'EduLab',                       'エデュラボ',                     'small'),
    ('4783', 'NCD',                          'NCD',                            'small'),
    ('3744', 'SIOS Technology',              'サイオス',                       'small'),
    ('3681', 'V-cube',                       'ブイキューブ',                   'small'),
    ('4344', 'Source Next',                  'ソースネクスト',                  'small'),
    ('3911', 'Aiming',                       'エイミング',                     'small'),
    ('3760', 'Cave',                         'ケイブ',                         'small'),
    ('3668', 'Colopl',                       'コロプラ',                       'small'),
    ('3656', 'KLab',                         'KLab',                           'small'),
    ('3928', 'Mynet',                        'マイネット',                     'small'),
    ('3653', 'Morpho',                       'モルフォAIソリューションズ',      'small'),
    ('4488', 'AI inside',                    'AIinside',                       'small'),
    ('4477', 'BASE',                         'BASE',                           'small'),
    ('6618', 'HeroZ',                        'ヒーローズ',                     'small'),
    ('3858', 'Ubiquitous AI',                'ユビキタスAI',                   'small'),
    ('2326', 'Digital Arts',                 'デジタルアーツ',                  'small'),
    ('3825', 'Remixpoint',                   'リミックスポイント',              'small'),
    ('7374', 'Sharing Innovations',          'シェアリングイノベーション',      'small'),
    ('4071', 'Plus Alpha Consulting',        'プラスアルファ・コンサルティング', 'small'),
    ('3909', 'Showcase',                     'ショーケース',                   'small'),
    ('3983', 'ORO',                          'オロ',                           'small'),
    ('4442', 'Kubell',                       'クベル',                         'small'),
    ('9416', 'Vision',                       'ビジョン',                       'small'),
    ('4293', 'Septeni Holdings',             'セプテーニ・ホールディングス',    'small'),
    ('9889', 'JBCC Holdings',               'JBCCホールディングス',            'small'),
    ('4005', 'Collabos',                     'コラボス',                       'small'),
    ('4480', 'Medley',                       'メドレー',                       'small'),
    ('4722', 'Future',                       'フューチャー',                   'small'),
    ('2371', 'Kakaku.com',                   '価格.com',                       'small'),
    ('4755', 'Rakuten Group',                '楽天グループ',                   'small'),
    ('3776', 'Broadmedia',                   'ブロードメディア',               'small'),
]

# Quick lookup dicts
TICKER_TO_NAME = {t: n for t, n, nj, sz in IT_UNIVERSE}
TICKER_TO_NAME_JP = {t: nj for t, n, nj, sz in IT_UNIVERSE}
TICKER_TO_SIZE = {t: sz for t, n, nj, sz in IT_UNIVERSE}

SIZE_LABELS_JP = {'large': '大型', 'mid': '中型', 'small': '小型'}
