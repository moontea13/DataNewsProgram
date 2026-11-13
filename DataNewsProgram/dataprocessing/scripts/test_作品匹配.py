"""季数和版本边界的回归检查：python3 -m unittest discover -s scripts -p 'test_作品匹配.py'。"""
import unittest
from 作品匹配 import cn_number, normalize, parse_title, visible_before_month_end


class TitleBoundaryTests(unittest.TestCase):
    def test_chinese_numbers(self):
        for text, expected in [("十", 10), ("十一", 11), ("二十五", 25), ("一百零一", 101), ("35", 35)]:
            self.assertEqual(cn_number(text), expected)

    def test_explicit_season_variants(self):
        a = parse_title("持械入宋：第九季")
        b = parse_title("持械入宋:第9季")
        self.assertEqual(a["title_key"], b["title_key"])
        self.assertEqual(a["season_number"], 9)

    def test_seasons_are_distinct_works(self):
        self.assertNotEqual(parse_title("万妖图录传第十季")["title_key"], parse_title("万妖图录传第十一季")["title_key"])

    def test_unmarked_is_not_first_season(self):
        self.assertEqual(parse_title("万妖图录传")["season_number"], "")
        self.assertNotEqual(parse_title("万妖图录传")["title_key"], parse_title("万妖图录传第一季")["title_key"])

    def test_numbers_inside_title_are_not_seasons(self):
        for title in ["1977山猎重生，我以余生偿前错", "我年终奖80W降到1W9，领导却慌了", "觉醒伪神：神明弃我我自为神6"]:
            self.assertEqual(parse_title(title)["season_number"], "")

    def test_remake_is_distinct(self):
        self.assertNotEqual(parse_title("咱家剑宗团宠小师妹真人版")["title_key"], parse_title("咱家剑宗团宠小师妹")["title_key"])

    def test_no_semantic_alias_merge(self):
        self.assertNotEqual(normalize("满宝进山闻香，山珍全归我家"), normalize("满宝进山闻香，山货全归我家"))

    def test_part_and_season_are_distinct(self):
        self.assertNotEqual(parse_title("故事第二部")["title_key"], parse_title("故事第二季")["title_key"])

    def test_future_same_name_version_excluded(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        boundary=int(datetime(2026,8,1,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp())
        self.assertTrue(visible_before_month_end({'first_visible_time':str(boundary-1)},'2026-07'))
        self.assertFalse(visible_before_month_end({'first_visible_time':str(boundary)},'2026-07'))
        self.assertTrue(visible_before_month_end({'first_visible_time':''},'2026-07'))


if __name__ == "__main__":
    unittest.main()
