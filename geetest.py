import os
import re

import jinja2
import hoshino
from hoshino import config
from quart import Blueprint

from .aiorequests import get


def has_port(string):
    pattern = r":\d+"  # 匹配冒号后面的一个或多个数字（端口号）
    return re.search(pattern, string) is not None


if hasattr(config, "PUBLIC_ADDRESS") and getattr(config, "PULIC_ADDRESS"):
    public_address = getattr(config, 'PUBLIC_ADDRESS')
elif hasattr(config, "IP") and getattr(config, "IP"):
    public_address = f"{getattr(config, 'IP')}:{getattr(config, 'PORT')}"
else:
    try:
        res = get(url=f"https://4.ipw.cn").text
        public_address = f"{res}:{getattr(config, 'PORT')}"
    except:
        public_address = "获取bot地址失败"

local_url_head = f"http://{public_address}/geetest/" if has_port(public_address) else f"https://{public_address}/geetest/"

template_folder = os.path.join(os.path.dirname(__file__), 'geetest')
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_folder),
    enable_async=True
)


async def render_template(template, **kwargs):
    t = env.get_template(template)
    return await t.render_async(**kwargs)


geetest_validate = Blueprint('geetest_validate', __name__)


@geetest_validate.route('/geetest')
async def geetest():
    return await render_template('geetest.html')


hoshino.get_bot().server_app.register_blueprint(geetest_validate)
