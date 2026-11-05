"""Public restaurant details verified from the owner's Facebook page."""

PROFILE = {
    'name': 'ร้านส้มตำ เมี่ยงคำ',
    'short_name': 'ส้มตำ เมี่ยงคำ',
    'location': 'อ.ทุ่งสง จ.นครศรีธรรมราช',
    'phone': '075 421 787',
    'phone_link': '075421787',
    'hours': 'อังคาร–อาทิตย์ 10:30–16:30 น.',
    'closed_day': 'หยุดทุกวันจันทร์',
    'facebook': 'https://www.facebook.com/somtammiangkham',
    'line': 'https://lin.ee/rMaxkwh',
    'verified_on': '2026-10-27',
}


def accepts_bookings_on(day):
    return day.weekday() != 0
