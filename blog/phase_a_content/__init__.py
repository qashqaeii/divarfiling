"""مقالات فاز A — SEO_CONTENT_PLAN."""
from blog.phase_a_content.article_01_crm_raygan import ARTICLE as A01
from blog.phase_a_content.article_02_peigiri import ARTICLE as A02
from blog.phase_a_content.article_03_chetor_download import ARTICLE as A03
from blog.phase_a_content.article_04_moghayese import ARTICLE as A04
from blog.phase_a_content.article_05_crm_vs_excel import ARTICLE as A05

PHASE_A_ARTICLES: dict[str, dict] = {
    A01['slug_base']: A01,
    A02['slug_base']: A02,
    A03['slug_base']: A03,
    A04['slug_base']: A04,
    A05['slug_base']: A05,
}
