# -*- coding: utf-8 -*-
'''
    Copyright (C) 2017 Gitcoin Core

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.

'''

import json

from django.conf import settings
from django.http import Http404, JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

import twitter
from ethos.models import Hop, ShortCode
from gas.utils import recommend_min_gas_price_to_confirm_in_time
from ratelimit.decorators import ratelimit
from retail.helpers import get_ip
from web3 import HTTPProvider, Web3

w3 = Web3(HTTPProvider(settings.WEB3_HTTP_PROVIDER))


@csrf_exempt
@ratelimit(key='ip', rate='5/m', method=ratelimit.UNSAFE, block=True)
def redeem_coin(request, shortcode):
    print(shortcode)

    if request.body:
        status = 'OK'

        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        try:
            twitter_api = get_twitter_api()

            if not twitter_api:
                raise Exception(_('Error while setting up Twitter API'))

            address = body['address']
            username = body['username']

            twitter_api.GetUser(screen_name=username)

            profile_pic = 'https://twitter.com/{}/profile_image?size=original'.format(username)

            ethos = ShortCode.objects.get(shortcode=shortcode)

            user_hop = Hop.objects.filter(shortcode=ethos, twitter_username=username, web3_address=address).order_by('-id').first()

            # Restrict same user from redeeming the same coin within 30 minutes
            if user_hop and (timezone.now() - user_hop.created_on).total_seconds() < 1800:
                raise Exception(_('Duplicate transaction detected'))

            address = Web3.toChecksumAddress(address)

            abi = json.loads('[{"constant":true,"inputs":[],"name":"mintingFinished","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transferFrom","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_amount","type":"uint256"}],"name":"mint","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"version","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_subtractedValue","type":"uint256"}],"name":"decreaseApproval","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[],"name":"finishMinting","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[],"name":"owner","outputs":[{"name":"","type":"address"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_addedValue","type":"uint256"}],"name":"increaseApproval","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},{"constant":false,"inputs":[{"name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"},{"payable":false,"stateMutability":"nonpayable","type":"fallback"},{"anonymous":false,"inputs":[{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"amount","type":"uint256"}],"name":"Mint","type":"event"},{"anonymous":false,"inputs":[],"name":"MintFinished","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"previousOwner","type":"address"},{"indexed":true,"name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"owner","type":"address"},{"indexed":true,"name":"spender","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')

            # Instantiate EthOS contract
            contract = w3.eth.contract(settings.ETHOS_CONTRACT_ADDRESS, abi=abi)

            tx = contract.functions.transfer(address, 1 * 10**18).buildTransaction({
                'nonce': w3.eth.getTransactionCount(settings.ETHOS_ACCOUNT_ADDRESS),
                'gas': 100000,
                'gasPrice': recommend_min_gas_price_to_confirm_in_time(5) * 10**9
            })

            signed = w3.eth.account.signTransaction(tx, settings.ETHOS_ACCOUNT_PRIVATE_KEY)
            transaction_id = w3.eth.sendRawTransaction(signed.rawTransaction).hex()

            previous_hop = Hop.objects.filter(shortcode=ethos).order_by('-id').first()

            Hop.objects.create(
                shortcode=ethos,
                ip=get_ip(request),
                created_on=timezone.now(),
                txid=transaction_id,
                web3_address=address,
                twitter_username=username,
                twitter_profile_pic=profile_pic,
                previous_hop=previous_hop
            )

            message = transaction_id

            tweet_to_twitter()
        except ShortCode.DoesNotExist:
            status = 'error'
            message = _('Bad request')
        except Exception as e:
            status = 'error'

            if 'User not found' in str(e):
                message = _('Please enter a valid Twitter username')
            else :
                message = str(e)

        # http response
        response = {
            'status': status,
            'message': message,
        }

        return JsonResponse(response)

    try:
        ShortCode.objects.get(shortcode=shortcode)

        params = {
            'class': 'redeem',
            'title': _('EthOS Coin'),
            'coin_status': _('INITIAL')
        }

        return TemplateResponse(request, 'redeem_ethos.html', params)
    except ShortCode.DoesNotExist:
        raise Http404


def tweet_to_twitter():
    """Tweet the EthOS redemption.

    Args:


    Returns:
        bool: Whether or not the twitter notification was sent successfully.

    """
    twitter_api = get_twitter_api()

    if not twitter_api:
        return False

    tweet_txt = "Redeemed EthOS Coin successfully: \n\n #EthOS"

    try:
        twitter_api.PostUpdate(tweet_txt)
    except Exception as e:
        print(e)
        return False

    return True


def get_twitter_api():
    if not settings.ETHOS_TWITTER_CONSUMER_KEY:
        return False

    twitter_api = twitter.Api(
        consumer_key=settings.ETHOS_TWITTER_CONSUMER_KEY,
        consumer_secret=settings.ETHOS_TWITTER_CONSUMER_SECRET,
        access_token_key=settings.ETHOS_TWITTER_ACCESS_TOKEN,
        access_token_secret=settings.ETHOS_TWITTER_ACCESS_SECRET,
    )

    return twitter_api
