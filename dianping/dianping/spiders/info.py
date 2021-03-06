# coding=utf-8
from os.path import join, dirname, abspath, pardir
from BeautifulSoup import BeautifulSoup

from scrapy.http import Request
from scrapy.contrib.spiders import CrawlSpider, Rule
from scrapy.contrib.linkextractors.sgml import SgmlLinkExtractor
from scrapy.selector import HtmlXPathSelector

from dianping.items import DianpingShopItem
from dianping import settings

class ShopDetailSpider(CrawlSpider):
    name = 'dianping.info'
    allowed_domains = ['dianping.com']
    rules = (
        Rule(SgmlLinkExtractor(allow=('shop/\d+(\?KID=\d+)?$'), deny=('.+/map$'), unique=True),callback='parse_shop_detail'), # shop detail
        Rule(SgmlLinkExtractor(allow=('search/category/\d+/.+\d+$'), restrict_xpaths="//div[@class='block ep-channels-wrapper']", unique=True)), # category pages
        Rule(SgmlLinkExtractor(allow=('.+\d+p\d+(n\d+)?/?.*$'), restrict_xpaths="//a[@class='NextPage']", unique=True)), # next page
        # Rule(SgmlLinkExtractor(allow=('[a-z]+'), restrict_xpaths="//div[@id='divPY']")), # city page
    )

    # start_urls = ['http://www.dianping.com/citylist',]
    # start_urls = ['http://www.dianping.com/search/category/9/10/r1629g4479',]
    
    # detail page
    #start_urls = ['http://www.dianping.com/shop/4719387?KID=74659',]

    # list page (no next page)
    # start_urls = ['http://www.dianping.com/search/category/2/10/g1851r2578j104k111x121y200/r14g10g355g1851r2578k111j104x121y200',]

    # list page (with next page)
    # start_urls = ['http://www.dianping.com/search/category/2/10/g328',]

    # crawled page
    # start_urls = ['http://www.dianping.com/shop/3873886',]

    def start_requests(self):
        if 'SEEDS' in settings.__dict__.keys():
            for seed in settings.SEEDS[self.name]:
                yield Request(seed, dont_filter=True)
        elif 'SEED_FILE' in settings.__dict__.keys():
            for line in open(settings.SEED_FILE,'r').readlines():
                if line.startswith('#'): continue
                yield Request(line.strip(), dont_filter=True)
        else:
            raise KeyError('neither SEEDS nor SEED_FILE defined in settings.py')

    def parse_shop_detail(self, response):
        hxs = HtmlXPathSelector(response)

        # Link url
        item = DianpingShopItem()
        item['link_url'] = response.url

        # Name
        name_elem = hxs.select("//h1[@class='shop-title']/text()").extract()
        if name_elem:
            item['name'] = name_elem[0]

        # Ratings
        # Address / Telephone
        # Category
        rating_elem = hxs.select("//meta[@itemprop='rating']/@content").extract()
        if rating_elem:
            item['rating'] = float(rating_elem[0])
        desc_elem = hxs.select("//div[@class='desc-list']/dl").extract()
        for elem in desc_elem:
            elem_obj = BeautifulSoup(elem)
            text = elem_obj.find('dt').text
            if text.startswith('口味'.decode('utf-8')):
                if elem_obj.find('em').text != '-':
                    item['taste_rating'] = int(elem_obj.find('em').text)
            if text.startswith('服务'.decode('utf-8')):
                if elem_obj.find('em').text != '-':
                    item['service_rating'] = int(elem_obj.find('em').text)
            if text.startswith('环境'.decode('utf-8')):
                if elem_obj.find('em').text != '-':
                    item['atmosphere_rating'] = int(elem_obj.find('em').text)
            if text.startswith('地址'.decode('utf-8')):
                item['address'] = elem_obj.find('dd').text
            if text.startswith('电话'.decode('utf-8')):
                item['tel'] = elem_obj.find('strong').text
            if text.startswith('分类'.decode('utf-8')):
                item['category'] = [a.text for a in elem_obj.findAll('a')]

        # Number of rating
        n_rating_elem = hxs.select("//span[@itemprop='count']/text()").extract()
        if n_rating_elem:
            try:
                item['n_rating'] = int(n_rating_elem[0])
            except: pass

        # Average Cost
        avg_cost_elem = hxs.select("//span[@class='Price']/../text()").extract()
        if avg_cost_elem:
            try:
                item['avg_cost'] = int(avg_cost_elem[0])
            except: pass

        # Bread crumb
        bread_crumb_elem = hxs.select("//div[@class='breadcrumb']").extract()
        if bread_crumb_elem:
            item['bread_crumb'] = BeautifulSoup(bread_crumb_elem[0]).text

        # Details (Description, Atmosphere, Feature, Landmark, Hours, Transportation)
        detail_elem = hxs.select("//div[@class='block-inner desc-list']/dl").extract()
        for elem in detail_elem:
            elem_obj = BeautifulSoup(elem)
            text = elem_obj.find('dt').text
            if text.startswith('商户描述'.decode('utf-8')):
                item['description'] = elem_obj.find('dd').text
            if text.startswith('推荐菜'.decode('utf-8')):
                item['recommend_list'] = self.parse_name_count(elem_obj)
            if text.startswith('餐厅氛围'.decode('utf-8')):
                item['atmosphere_list'] = self.parse_name_count(elem_obj, 'span')
            if text.startswith('餐厅特色'.decode('utf-8')):
                item['feature_list'] = self.parse_name_count(elem_obj, 'span')
            if text.startswith('商区地标'.decode('utf-8')):
                item['landmark_bread_crumb'] = elem_obj.find('dd').text
            if text.startswith('营业时间'.decode('utf-8')):
                item['hours'] = elem_obj.find('dd').text
            if text.startswith('公交信息'.decode('utf-8')):
                item['transport'] = elem_obj.find('dd').text

        # remove tailing '站' in city name
        loc_elem = hxs.select("//a[@id='G_loc']/span/text()").extract()
        if loc_elem:
            site_name = loc_elem[0]
            head,sep,tail = site_name.rpartition('站'.decode('utf-8'))
            if sep=='':
                item['city'] = site_name
            else:
                item['city'] = head

        return item

    def parse_name_count(self, beautifulsoup_tag, tag_name='strong'):
        ret = []
        for elem in beautifulsoup_tag.findAll(tag_name):
            name = elem.find('a').text
            if not name.startswith('更多'.decode('utf-8')):
                count = int(elem.find('em').text[1:-1])
                ret.append( (name,count,))
        return ret

