from BiliClient import asyncbili
import logging, json
from .import_once import now_time

async def clean_dynamic_task(biliapi: asyncbili,
                       task_config: dict
                       ) -> None:
    try:
        async for x in get_space_dynamic(biliapi):
            dyid = x["desc"]["dynamic_id"]
            card = json.loads(x["card"])

            if 'item' in card and 'miss' in card["item"] and card["item"]["miss"] == 1:
                await biliapi.removeDynamic(dyid)
                logging.info(f'{biliapi.name}: 已删除id为{dyid}的动态，原因为：动态已被原作者删除')
                continue
            
            if 'origin_extension' in card and 'lott' in card["origin_extension"]:
                lott = json.loads(card["origin_extension"]["lott"])
                if 'lottery_time' in lott and lott["lottery_time"] <=  now_time:
                    await biliapi.removeDynamic(dyid)
                    logging.info(f'{biliapi.name}: 已删除id为{dyid}的动态，原因为：过期抽奖')
                    continue

            if 'item' in card and 'orig_dy_id' in card["item"]:
                ret = (await biliapi.getLotteryNotice(card["item"]["orig_dy_id"]))["data"]
                if 'lottery_time' in ret and ret["lottery_time"] <= now_time:
                    await biliapi.removeDynamic(dyid)
                    logging.info(f'{biliapi.name}: 已删除id为{dyid}的动态，原因为：过期抽奖')
                    continue

            if 'origin' in card:
                origin = json.loads(card["origin"])
                if 'item' in origin and 'description' in origin["item"]:
                    if 'description' in card["item"]:
                        text = origin["item"]["description"]
                    elif 'content' in card["item"]:
                        text = card["item"]["content"]
                    else:
                        text = None
                    if text:
                        for x in task_config["black_keywords"]:
                            if x in text:
                                await biliapi.removeDynamic(dyid)
                                logging.info(f'{biliapi.name}: 已删除id为{dyid}的动态，原因为：包含黑名单关键字{x}')
                                continue

            if task_config.get("unfollowed", False):
                if 'origin' in x["desc"] and 'uid' in x["desc"]["origin"]:
                    try:
                        ret = await biliapi.getRelationByUid(x["desc"]["origin"]["uid"])
                    except Exception as e: 
                        logging.info(f'{biliapi.name}: 判断与动态{dyid}的作者关系时异常，原因为{str(e)}，跳过此动态的清理')
                    else:
                        if ret["code"] == 0:
                            if ret["data"]["attribute"] == 0:
                                await biliapi.removeDynamic(dyid)
                                logging.info(f'{biliapi.name}: 已删除id为{dyid}的动态，原因为：源动态作者没被关注')
                                continue
                        else:
                            logging.info(f'{biliapi.name}: 判断与动态{dyid}的作者关系时异常，原因为{ret["message"]}，跳过此动态的清理')

    except Exception as e: 
        logging.warning(f'{biliapi.name}: 获取动态列表、异常，原因为{str(e)}，跳过动态清理')

async def get_space_dynamic(biliapi: asyncbili) -> dict:
    '''取B站用户动态数据，异步生成器'''
    offset = ''
    hasnext = True
    retry = 3 #连续失败重试次数
    while hasnext:
        try:
            ret = await biliapi.getSpaceDynamic(offset_dynamic_id=offset)
        except Exception as e: 
            if retry:
                retry -= 1
                logging.warning(f'{biliapi.name}: 获取空间动态列表异常，原因为{str(e)}，重试空间动态列表获取')
            else:
                logging.warning(f'{biliapi.name}: 获取空间动态列表异常，原因为{str(e)}，跳过获取')
                break
        else:
            if ret["code"] == 0 and ret["data"]:
                hasnext = (ret["data"]["has_more"] == 1)
                if 'cards' in ret["data"] and ret["data"]["cards"]:
                    for x in ret["data"]["cards"]:
                        yield x
                    offset = x["desc"]["dynamic_id_str"]
                    retry = 3
                else:
                    retry -= 1
            else:
                retry -= 1
                logging.warning(f'{biliapi.name}: 获取空间动态列表失败，信息为{ret["message"]}，重试获取')

            if not retry:
                logging.warning(f'{biliapi.name}: 获取空间动态列表失败次数太多，跳过获取')
                break