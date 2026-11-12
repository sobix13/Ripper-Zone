# Release 1.1.0 acceptance and traceability

The 138 baseline requirement IDs are retained. Automated checks cover the accounting, real SDK serialization, selected native UI workflows, source adapters, authorization, concurrent operations and deployment simulation. A requirement marked implemented below is not a claim that production Discord or VPS acceptance was performed.

Run all 64 live/operational gates from the baseline audit on the upgraded server where applicable. In particular: actual permissions and private logs, real source event roster counts, moderator reactions, role hierarchy, ticket reservations/refunds, public message recovery, source helper, backups and iOS/desktop rendering.

## Requirement matrix

| ID | Area / requirement | Release disposition |
| --- | --- | --- |
| R001 | هویت · نام پذیرفته‌شده Ripper Zone | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R002 | هویت · RC مخفف Ripper Credit، جمع Ripper Credits | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R003 | هویت · بات مستقل از Melee و بدون انتقال موجودی MC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R004 | اقتصاد · یک حساب RC برای تسک، رویداد، پاداش دستی و اسپین | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R005 | پنل عضو · شروع کار از پیام عمومی و دکمه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R006 | پنل عضو · خانه کاربردی با وضعیت فعالیت‌های قابل انجام | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R007 | پنل عضو · نمایش Available، Reserved و Earned با معنای روشن | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R008 | پنل عضو · تاریخچه قابل مرور | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R009 | پنل عضو · مشارکت‌ها و پاداش‌های خود فرد در تسک | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R010 | پنل عضو · عملکرد هفتگی و ماهانه، معادل بخش مفید Dashboard ملی زون | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R011 | پنل عضو · آرشیو رافل‌ها و جوایز خود فرد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R012 | پنل عضو · همه بخش‌ها از دکمه و انتخاب‌گر، بدون نیاز روزمره به کامند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R013 | پنل عضو · مسیر بازگشت، وضعیت بارگذاری و پایان اعتبار صفحه | Private expiration guidance implemented; real-client timeout handling remains in live acceptance. |
| R014 | لیدربورد · لیدربورد عمومی واقعاً منتشر و متصل شود | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R015 | لیدربورد · دکمه‌های عمومی دوره و My Rank | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R016 | لیدربورد · یک قرارداد رتبه مساوی در همه صفحه‌ها | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R017 | لیدربورد · دسترسی به افراد بعد از رتبه دهم | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R018 | لیدربورد · نمایش رتبه خود فرد حتی خارج از ده نفر اول | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R019 | لیدربورد · هفته تقویمی، مشابه ملی زون | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R020 | لیدربورد · رتبه روزانه و ماهانه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R021 | لیدربورد · رتبه از درآمد معتبر، نه موجودی قابل خرج | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R022 | لیدربورد · انتشار و Refresh از پنل مدیریت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R023 | لیدربورد · نمایش دوره فعال، آخرین به‌روزرسانی و وضعیت خالی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R024 | تسک · ساخت تسک عمومی با ترد اختصاصی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R025 | تسک · فرم ساده با فیلدهای جداگانه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R026 | تسک · نمایش کامل متن، مبلغ و مهلت در ترد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R027 | تسک · مدیریت تسک‌های فعال و گذشته از پنل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R028 | تسک · آمار ارسال‌کنندگان و پاداش‌گرفته‌ها | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R029 | تسک · ویرایش عنوان و توضیح بعد از ساخت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R030 | تسک · ویرایش مبلغ پایه با سیاست مشخص | Base reward locks after participation; closed timing locks. Duplicate creates a new policy. |
| R031 | تسک · ویرایش cooldown و deadline و همگامی پیام | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R032 | تسک · نمایش جزئیات برای عضو از خود پنل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R033 | تسک · پرداخت پایه یکتا در هر دوره | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R034 | تسک · پاداش کیفیت مستقل از پایه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R035 | تسک · مدیریت پایان، بستن و آرشیو با تلاش مجدد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R036 | تسک · شناخت دوره بدون حفظ task_id و cycle_id | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R037 | تسک · ثبت پست در زمان آفلاین با بررسی ماد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R038 | تسک · Cooldown و معافیت مادها | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R039 | تسک · Reset Cooldown یک عضو از پنل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R040 | تسک · محافظت کانال اصلی تسک مثل ملی زون | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R041 | تسک · ساخت همزمان بدون دو ترد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R042 | تسک · بازیابی ترد و پیام بدون ارسال تکراری | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R043 | ری‌اکشن · مشاهده همه ایموجی‌ها و RC در پنل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R044 | ری‌اکشن · افزودن، ویرایش و حذف rule با فرم | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R045 | ری‌اکشن · تفاوت مبلغ پایه با مبلغ ثابت ایموجی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R046 | ری‌اکشن · ایموجی یونیکد و سفارشی، حداکثر پنج rule | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R047 | ری‌اکشن · مبلغ صفر کیفیت از Import هم پذیرفته نشود | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R048 | ری‌اکشن · عملیات یکتا با تغییر ماد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R049 | ری‌اکشن · خطای موقت شبکه پاداش را گم نکند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R050 | ری‌اکشن · بازیابی ری‌اکشن‌های جامانده | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R051 | ری‌اکشن · تغییر مقدار برای آینده، بدون دستکاری گذشته | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R052 | ری‌اکشن · حذف ری‌اکشن، حذف خودکار پول نباشد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R053 | ری‌اکشن · سیاست ری‌اکشن ماد روی پست خودش | Another moderator must approve automatic/reviewed task rewards. General manual bonuses remain explicit moderator actions. |
| R054 | ری‌اکشن · پاداش پیام خارج از ترد تسک و منوی پیام | Message context menu restores general manual awards. Automatic reactions are deliberately limited to managed task threads. |
| R055 | اسنپ‌شات · اسنپ‌شات تسک بدون فایل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R056 | اسنپ‌شات · اسنپ‌شات چنل یا ترد و بازه زمانی مثل ملی زون | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R057 | اسنپ‌شات · اسنپ‌شات افراد ری‌اکت‌کرده به پیام | Reaction snapshot implemented with human filtering, paginated enumeration, cap and explicit confirmation. |
| R058 | اسنپ‌شات · رویداد رامبل و رافل بدون فایل در کار روزمره | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R059 | اسنپ‌شات · رامبل شامل برنده و بازنده‌ها | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R060 | اسنپ‌شات · رافل عادی شامل شرکت‌کنندگان، حتی بازنده | Preserves the original eligible pool including losers. Excluded source entrants are not silently reclassified as eligible. |
| R061 | اسنپ‌شات · پاداش رافل عادی از خرید تیکت RC جدا باشد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R062 | اسنپ‌شات · منبع واقعی و اطلاعات معتبر رویداد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R063 | اسنپ‌شات · پیش‌نمایش مخاطبان و جمع RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R064 | اسنپ‌شات · تکرار واردکردن رویداد پول دوباره ندهد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R065 | اسنپ‌شات · پست ثبت‌شده با تأیید کیفی ماد اشتباه نشود | Presence is explicitly labeled separately from approval; a cycle snapshot is deliberate moderator batch approval, not peer review. |
| R066 | پاداش دستی · انتخاب فرد با UserSelect | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R067 | پاداش دستی · Preview و تأیید یکتا | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R068 | پاداش دستی · مشاهده حساب هر عضو در پنل مدیریت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R069 | پاداش دستی · Correction مثبت و منفی با دلیل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R070 | پاداش دستی · Revoke پاداش نامعتبر و حذف metric مرتبط | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R071 | پاداش دستی · نتیجه بعد از commit با خطای ارسال متناقض نباشد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R072 | رافل RC · فیچر مستقل با پست عمومی و خرید تیکت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R073 | رافل RC · فرم قواعد قابل فهم با فیلد جدا | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R074 | رافل RC · ذخیره و ویرایش Draft پیش از انتشار | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R075 | رافل RC · رزرو اتمیک، جلوگیری از دوباره‌خرج‌کردن و سقف تیکت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R076 | رافل RC · قرارداد قیمت و دسترسی ثابت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R077 | رافل RC · پیش‌نمایش مبلغ خرید و رسید | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R078 | رافل RC · حداقل افراد، refund و خطای نامعلوم eligibility | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R079 | رافل RC · تعداد جایزه با تعداد افراد واجدشرایط سازگار باشد | Public rules say up to N winners; fewer eligible members never promise a guaranteed N prizes. |
| R080 | رافل RC · فهرست، بستن، لغو و Refresh از پنل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R081 | رافل RC · نمایش برندگان جاری بعد از replacement | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R082 | رافل RC · Claim از My Prizes، مستقل از پیدا کردن پست قدیمی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R083 | رافل RC · تحویل، forfeiture و replacement با دلیل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R084 | رافل RC · Proof نتیجه بدون قرعه‌کشی دوباره | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R085 | رول · سه رول اختیاری و قابل Skip در Wizard | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R086 | رول · RoleSelect و metricهای جداگانه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R087 | رول · ذخیره خاموش و فعال‌سازی بعدی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R088 | رول · تعریف روشن task/event count | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R089 | رول · فقط بالاترین سطح و افزودن قبل از حذف | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R090 | رول · حفاظت منابع Gate، Crew، Raffle و رول‌های دسترسی | Configured access/staff and foreign registered roles protected; dedicated-role guidance added. Unknown manual role purpose is not guessed. |
| R091 | اسپین · ده خروجی بین 2 و 100 | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R092 | اسپین · شانس 100 RC برابر نیم درصد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R093 | اسپین · میانگین کل 5 RC و حداقل 2 | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R094 | اسپین · روزی یک بار با بازشدن پنل و کلیک روزانه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R095 | اسپین · ریست روز UTC و عبور درخواست از نیمه‌شب | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R096 | اسپین · تجربه نمایش اسپین و نتیجه قابل بازگشت | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R097 | اسپین · فعال یا غیرفعال‌کردن از پنل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R098 | برندینگ · استفاده گزینشی از تصاویر رامبل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R099 | برندینگ · قابل ویرایش بودن عنوان و پیام خوشامد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R100 | برندینگ · About و Support قابل تنظیم | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R101 | برندینگ · ویرایش متن‌های اعلان و پیام‌های عمومی مرتبط | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R102 | برندینگ · متن پویا و متغیرهای مجاز بدون اجرای کد | Whitelisted placeholders supported for twenty templates; five core copy fields use literal text. Financial facts remain separate. |
| R103 | برندینگ · ویرایش پیام و نتیجه در همه مسیرها هماهنگ بمانند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R104 | راهنما · راهنمای عضو چندصفحه‌ای و متناسب با RC | Contextual member guide and configurable support copy; existing Crew channel link is selectable. |
| R105 | راهنما · راهنمای مدیر داخل بات | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R106 | ستاپ · نمایش کامل تنظیمات فعلی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R107 | ستاپ · ویرایش یک چنل بدون تکرار کل Wizard | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R108 | ستاپ · جابجایی چنل، شناسه پیام قدیمی را خراب نکند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R109 | ستاپ · دسترسی مادها و مدیران اصلی از انتخاب‌گر | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R110 | ستاپ · تاریخچه، Import و Export تنظیمات | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R111 | ستاپ · جلوگیری از بازنویسی فرم قدیمی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R112 | ستاپ · اتمام Wizard با وضعیت روشن و Publishهای لازم | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R113 | ستاپ · Pause برنامه بدون گم‌کردن رزروهای موجود | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R114 | امنیت · عضو دیگر نتواند پنل خصوصی را کنترل کند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R115 | امنیت · دسترسی تازه در لحظه عملیات | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R116 | امنیت · عدد صحیح و validation، بدون امتیاز اعشاری MC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R117 | امنیت · لاگ ماد واقعاً خصوصی باشد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R118 | حسابداری · تراکنش اتمیک، idempotency و حفظ RC در retry | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R119 | حسابداری · برگشت به پشتیبان قدیمی خودکار انجام نشود | Legacy configuration/financial schema stays readable; old code cannot execute new presentation jobs. Re-upgrade and retry those jobs. |
| R120 | نصب · کاربر، سرویس، مسیر و پورت مستقل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R121 | نصب · فرم توکن و شناسه صاحب، خطای قابل اصلاح بدهد | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R122 | نصب · ارتقا با حفظ env و RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R123 | نصب · Rollback ناموفق سرویس سالم را خاموش رها نکند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R124 | نصب · بسته نهایی فایل حساس تو در تو را وارد نکند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R125 | عملیات · Health قابل فهم در پنل، نه فقط JSON | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R126 | عملیات · Retry jobs و بازیابی binding از دکمه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R127 | عملیات · Verified Missing محلی واقعاً کار کند | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R128 | عملیات · پشتیبان SQLite معتبر و روزانه | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R129 | عملیات · تربل‌شوت خودکار محدود و مستقل | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R130 | عملیات · Backup خارج VPS و استانداردهای کامل Crew | Offsite backup remains unconfigured; no destination or credentials were supplied. |
| R131 | کیفیت · تست عددی اسپین و رقابت چندپردازشی | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R132 | کیفیت · تست کل مسیر UI، نه فقط هسته | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R133 | کیفیت · تست user و root در CI | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R134 | کیفیت · پذیرش Discord و VPS واقعی | PENDING LIVE: no production Discord/VPS session was supplied to this implementation environment. |
| R135 | دامنه · Quiz و سیستم ثبت محتوا و peer review در این نسخه نباشند | Intentionally excluded: quiz, content submission and peer review. Task moderation remains implemented. |
| R136 | دامنه · رول‌ها بعداً با metric فعال شوند | Exactly three tiers use earned RC, rewarded task cycles and paid events. Purchase/holder/onchain metrics are not implemented. |
| R137 | دامنه · ثبت تصمیمات و نقشه کامل اجرا پیش از اصلاح جدید | Baseline audit requirement IDs retained here; implementation and test scope recorded separately from live acceptance. |
| R138 | دامنه · تغییرات محلی ناتمام با نسخه منتشرشده اشتباه نشوند | WIP integrated into 1.1.0; release staging and CI must pass before installation. |

## Technical findings F01–F19

| Finding | Resolution |
| --- | --- |
| F01 | System actor zero is explicit; first leaderboard publication persists ID and clears marker. |
| F02 | A shared RANK query powers list and account, excludes zero scores and supports pagination/personal position. |
| F03 | Task briefs use Components V2 and persistent bindings; full 2000-character body and financial rules remain visible. |
| F04 | Reaction input is durable before external processing. Retries retain its original rule and financial identity. |
| F05 | Local verified-missing can persist the explicit system actor. |
| F06 | Task publication checks the conditional claim before creating a thread. |
| F07 | Unknown display failures no longer claim that no financial result exists. |
| F08 | Active quality rules reject zero; base uses amount=0 as a task-reward marker. Reactions have an explicit pause toggle. |
| F09 | Existing task quality identities return already recorded; rule changes do not top up old reactions. |
| F10 | Public raffle wording states an upper winner ceiling. |
| F11 | Bound-channel edits are refused; explicit movement durably publishes/binds then redirects the original post. |
| F12 | Forms retain the settings revision from opening. |
| F13 | Manual close uses the same durable archival job as automatic expiry. |
| F14 | Rollback checks an isolated backup before stopping services and restores prior active code/services on failure. |
| F15 | Member task lists require a bound thread and published status. |
| F16 | Source policy is explicit: original eligible ordinary-raffle participants including losers; complete Rumble final ranking. |
| F17 | Explicit log View Channel allows for unapproved roles/members are refused; actual server permission acceptance remains required. |
| F18 | Documentation and native tier setup state the exact protected scope and require dedicated roles; no claim of detecting unknown manual role purpose. |
| F19 | Nested env/key/WAL/SHM runtime artifacts are refused in release folders. |
