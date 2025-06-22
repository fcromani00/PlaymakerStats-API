from fastapi import FastAPI, HTTPException
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import pandas as pd
from io import StringIO

app = FastAPI()

@app.get("/player")
async def get_player_data(player_page_link: str):
    """
    Args:
        player_page_link (str): Envie o link da página do playmakerstats.com de um jogador.
        Ex: https://www.playmakerstats.com/player/richard-rios/744267

    Returns:
        json: Dicionário com as informações coletadas do perfil do jogador.
    """
    # 1. Validação do Link
    player_page_link = urlparse(player_page_link)
    # Reconstrói a URL sem a parte de query (?) ou fragmento (#)
    player_page_link = urlunparse(player_page_link._replace(query='', fragment=''))

    if not re.match(r'^https?://(www\.)?playmakerstats\.com/player/[^/]+/\d+', player_page_link):
        raise HTTPException(status_code=400, detail="URL inválida. O link deve ser do playmakerstats.com e seguir o formato de perfil de jogador.")

    # 2. Coletar o conteúdo da página
    try:
        response = requests.get(player_page_link, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Erro ao acessar a página: {e}. Verifique se o link está correto ou se há problemas de conexão.")

    soup = BeautifulSoup(response.content, "html.parser")

    # Inicializa o dicionário com valores padrão None
    dict_playmaker = {
      'Player ID': None,
      'Short Name': None,
      'Full Name': None,
      'Team':None,
      'Age':None,
      'Birth Date': None,
      'Nationality':None,
      'Citizenship':None,
      'Position':None,
      'Foot':None,
      'Height (cm)':None,
      'Market Value':None,
      'Contract Expires':None,
      'Player Agent': None,
      'Player Agent Link':None,
      'Player img url':None,
      'Team img url':None,
      'Instagram':None,
      'PlaymakerStats Profile': player_page_link
    }
    
    try:
        profile_soup = soup.find('div', class_='rbbox nofooter')  # Extraindo a div do PROFILE
  
        divs_bio_half = profile_soup.find_all('div', class_='bio_half')
        divs_bio = profile_soup.find_all('div', class_='bio')
    except:
        print("Erro ao extrair o div do PROFILE")

    #Player ID
    try:
        dict_playmaker['Player ID'] = re.compile(r'/player/[^/]+/(\d+)').search(player_page_link).group(1)
    except:
        dict_playmaker['Player ID'] = None

    #Short Name
    try:
        name_element = soup.find('div', class_='player_name').find('span')# Encontrando a tag <span> com a classe "name"
        if name_element:
            dict_playmaker['Short Name'] = name_element.get_text(strip=True)
    except:
        dict_playmaker['Short Name'] = None

    #Birth Date
    try:
        # Encontrando a tag que contém "Born/Age"
        bio_half_div = soup.find('div', class_='bio_half')
        born_age_element = bio_half_div.find('span', string='Born/Age')

        if born_age_element:
            # A data de nascimento está logo após o elemento <span> "Born/Age"
            birth_date = born_age_element.find_next_sibling(string=True).strip()
            if birth_date:
                dict_playmaker['Birth Date'] = birth_date
    except:
        dict_playmaker['Birth Date'] = None

    #foot
    try:
        for div in divs_bio_half:
            span = div.find('span')
            preferred_foot = None
            if span and 'Preferred foot' in span.text:
                dict_playmaker['Foot'] = div.text.split('Preferred foot')[1].strip().lower()
                break
    except:
        dict_playmaker['Foot'] = None

    try:
        # Encontrando a tag que contém a idade
        age_element = soup.find('div', class_='bio_half').find('span', class_='small').get_text(strip=True)
        if age_element:
            age = re.search(r'\((\d+) -yrs-old\)', age_element).group(1)
            dict_playmaker['Age'] = age
    except:
        dict_playmaker['Age'] = None

    try:
        # Encontrando a tag que contém o país de nascimento
        country_element = soup.find('div', class_='bio_half').find('div', class_='micrologo_and_text').find('div', class_='text').get_text(strip=True)
        if country_element:
            dict_playmaker['Nationality'] = country_element
    except:
        dict_playmaker['Nationality'] = None

    try:
        dual_nationality_found = False # Flag para saber se encontramos
        for div_half in divs_bio_half: # Itera sobre todas as divs 'bio_half'
            # Tenta encontrar o span 'Dual Nationality' dentro desta div_half
            span_dual_nationality = div_half.find('span', string='Dual Nationality')
            
            if span_dual_nationality:
                # Se encontrou o span, o micrologo_and_text correspondente é o próximo irmão dele
                micrologo_div = span_dual_nationality.find_next_sibling('div', class_='micrologo_and_text')
                
                if micrologo_div:
                    # Dentro do micrologo_and_text, encontra a div com a classe 'text'
                    text_div = micrologo_div.find('div', class_='text')
                    
                    if text_div:
                        dict_playmaker['Citizenship'] = text_div.get_text(strip=True)
                        dual_nationality_found = True
                        break # Sai do loop assim que encontrar (para pegar apenas a primeira, se houver mais)
        
        if not dual_nationality_found:
            dict_playmaker['Citizenship'] = None # Garante que seja None se não encontrar
            
    except Exception:
        dict_playmaker['Citizenship'] = None

    try:
        title = soup.find("title").get_text(strip=True)
        dict_playmaker['Team'] = re.search(r' - ([^-]+) - ', title).group(1).strip()
    except:
        dict_playmaker['Team'] =None

    try:
        meta_tag = soup.find("meta", {"name": "description"})['content']
        dict_playmaker['Full Name'] = re.search(r'^(.+?) is a \d+-year-old Football player', meta_tag).group(1).strip()
    except:
        dict_playmaker['Full Name'] = None

    try:
        position_td = soup.find('span', string='Position').find_next_sibling('tr').find_all('td')[1]
        dict_playmaker['Position'] = position_td.get_text(strip=True)
    except:
        dict_playmaker['Position'] = None

    # Vencimento do contrato
    try:
        # 1. Encontrar a span com a CLASSE 'label' e o texto 'Contract'
        contract_span = profile_soup.find('span', class_='label', string='Contract')
        
        if contract_span:
            contract_value_node = contract_span.next_sibling
            if contract_value_node and isinstance(contract_value_node, str):
                dict_playmaker['Contract Expires'] = contract_value_node.strip()
    except Exception:
        dict_playmaker['Contract Expires'] = None

    #player image and height
    try:
        script_tag = soup.find("script", type="application/ld+json").string
        dict_playmaker['Player img url'] = re.search(r'"image"\s*:\s*"([^"]+)"', script_tag).group(1)
    except:
        dict_playmaker['Player img url'] = None

    try:
        script_tag = soup.find("script", type="application/ld+json").string
        dict_playmaker['Height (cm)'] = int(re.search(r'"height"\s*:\s*"(\d+)', script_tag).group(1))
        if dict_playmaker['Height (cm)'] == 0:
            dict_playmaker['Height (cm)'] = None
    except:
        dict_playmaker['Height (cm)'] = None

    try:
        # Encontrar a tag <img> onde o title corresponde ao nome do time usando regex
        img_tag = soup.find("img", {"title": re.compile(re.escape(dict_playmaker['Team']))})
        dict_playmaker['Team img url'] = "https://www.playmakerstats.com" + img_tag['src']
    except:
        dict_playmaker['Team img url'] = None

    # Market Value
    try:
        # Encontrar a div 'rectangle' que tem o título "Market value"
        market_value_div = soup.find('div', class_='rectangle', title='Market value')
        
        if market_value_div:
            # Dentro dessa div, encontrar a div com a classe 'value'
            value_div = market_value_div.find('div', class_='value')
            
            if value_div:
                # O valor está dentro de um span dentro da div 'value'
                market_value_span = value_div.find('span')
                if market_value_span:
                    dict_playmaker['Market Value'] = market_value_span.get_text(strip=True).replace(' \x80', '')
    except Exception:
        dict_playmaker['Market Value'] = None

    try:
        agent_found = False # Flag para saber se encontramos
        for div_bio in divs_bio: # Itera sobre todas as divs 'bio'
            # Tenta encontrar o span 'Agent' dentro desta div_bio
            span_agent = div_bio.find('span', string='Agent')
            
            if span_agent:
                # O link do agente é o próximo irmão do span 'Agent'
                agent_link_tag = span_agent.find_next_sibling('a')
                
                if agent_link_tag:
                    # O nome do agente está no texto da tag <a>
                    dict_playmaker['Player Agent'] = agent_link_tag.get_text(strip=True)
                    
                    # O link do agente está no atributo 'href' da tag <a>
                    # Constrói a URL completa usando urljoin, pois pode ser relativa
                    dict_playmaker['Player Agent Link'] = requests.compat.urljoin(player_page_link, agent_link_tag['href'])
                    
                    agent_found = True
                    break # Sai do loop assim que encontrar
        
        if not agent_found: # Se não encontrou o agente em nenhuma div
            dict_playmaker['Player Agent'] = None
            dict_playmaker['Player Agent Link'] = None
            
    except Exception:
        dict_playmaker['Player Agent'] = None
        dict_playmaker['Player Agent Link'] = None

    # Instagram
    try:
        for div in divs_bio:
            if 'Other connections' in div.text:
                try:
                    instagram_link = div.find('a', href=re.compile(r'https://www.instagram.com/'))['href']
                    dict_playmaker['Instagram'] = "@" + re.search(r'https://www.instagram.com/([^/]+)', instagram_link).group(1)
                    break  # Se encontrar o Instagram, saia do loop
                except:
                    dict_playmaker['Instagram'] = None
    except:
        dict_playmaker['Instagram'] = None

    return dict_playmaker
