from __future__ import annotations

SAMPLE_CSV = (
    "MainIdentifier,PublisherName,SeriesName,IssueNumber,Title,FOCDate,InStoreDate,CoverPrice,VariantName,Ratio\n"
    "JUN260001,Image,Battle Beast,8,Battle Beast #8,2026-06-01,2026-06-24,4.99,Cover A,\n"
)

MULTI_VARIANT_CSV = (
    "MainIdentifier,PublisherName,MainDesc,IssueNumber,Title,FOCDate,InStoreDate,Retail\n"
    "0626DC0001,DC Comics,ZATANNA (2026),5,ZATANNA (2026) #5 CVR A JAMAL CAMPBELL,2026-06-01,2026-06-24,4.99\n"
    "0626DC0002,DC Comics,ZATANNA (2026),5,ZATANNA (2026) #5 CVR B DAVID TALASKI CARD STOCK VAR,2026-06-01,2026-06-24,4.99\n"
    "0626DC0003,DC Comics,ZATANNA (2026),5,ZATANNA (2026) #5 CVR C BRUNO REDONDO CARD STOCK VAR,2026-06-01,2026-06-24,4.99\n"
)

MOCK_LOGIN_HTML = """
<form action="/account/login" id="loginform" method="post">
<input name="__RequestVerificationToken" type="hidden" value="test-token" />
<input name="Username" type="text" />
<input name="Password" type="password" />
</form>
"""

MOCK_RESOURCES_HTML = """
<h2>Monthly CSV Product Files</h2>
<h3>June 2026</h3>
<a href="/files/june-2026-lunar-format.csv">Lunar Format Product File</a>
<a href="/files/june-2026-lunar-format-related.csv">Lunar Format Product File With Related Products</a>
<h3>May 2026</h3>
<a href="/files/may-2026-lunar-format.csv">Lunar Format Product File</a>
"""
