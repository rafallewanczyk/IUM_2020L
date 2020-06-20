# /usr/bin/python3
import pandas as pd
import numpy as np
import argparse
import seaborn as sns
import matplotlib.pyplot as plt

product_data = pd.read_json('resources/products.jsonl', lines=True)
product_data.set_index('product_id', inplace=True)
session_data = pd.read_json('resources/sessions.jsonl', lines=True)
users_data = pd.read_json('resources/users.jsonl', lines=True)

# find products with price lower or equal 0 and greater than 1000000 and those which have '#','&' or ';' in name
incorrect_products = product_data[
    (product_data["price"] <= 0) |
    (product_data["price"] > 1000000) |
    (product_data['product_name'].str.contains('#|;|&', regex=True))].index

# find values of their 'product_id' column


# drop incorrect products
product_data.drop(incorrect_products, inplace=True)
# change strings with categories into list of categories
product_data["category_path"] = product_data["category_path"].apply(lambda x: x.split(';'))

# drop rows with null value of columns 'user_id' or 'product_id'
session_data.dropna(subset=['user_id', 'product_id'], inplace=True)
session_data.drop(columns=['purchase_id'], inplace=True)

# replace floats with ints
session_data.user_id = session_data.user_id.astype(int)
session_data.product_id = session_data.product_id.astype(int)
# drop rows with products that are incorrect
incorrect_sessions = session_data[session_data["product_id"].isin(incorrect_products)].index
session_data.drop(incorrect_sessions, inplace=True)

users_data.drop(columns=['name', 'street'], inplace=True)

# set amount of rows print
pd.set_option('display.max_rows', 100)
all_session_ids = session_data.session_id.unique()


def getListOfCategories(product_data):
    a = set()
    for categories in product_data.category_path:
        for item in categories:
            a.add(item)
    return sorted(list(a))

category_weights = {
    'Gry i konsole': 1/3,
    'Gry komputerowe': 2/3,
    'Gry na konsole': 1/3,
    'Gry PlayStation3': 1/3,
    'Gry Xbox 360': 1/3,
    'Komputery': 1/3,
    'Drukarki i skanery': 1/3,
    'Biurowe urządzenia wielofunkcyjne': 1/3,
    'Monitory': 1/3,
    'Monitory LCD': 1/3,
    'Tablety i akcesoria': 1/3,
    'Tablety': 1/3,
    'Sprzęt RTV': 1/3,
    'Audio': 1/3,
    'Słuchawki': 1/3,
    'Przenośne audio i video': 1/3,
    'Odtwarzacze mp3 i mp4': 1/3,
    'Video': 1/3,
    'Odtwarzacze DVD': 1/3,
    'Telewizory i akcesoria': 1/6,
    'Anteny RTV': 1/6,
    'Okulary 3D': 1/6,
    'Telefony i akcesoria': 1/3,
    'Akcesoria telefoniczne': 1/3,
    'Zestawy głośnomówiące': 1/3,
    'Zestawy słuchawkowe': 1/3,
    'Telefony komórkowe': 2/3,
    'Telefony stacjonarne': 2/3
}

def categoryListIntoSeries(listSeries, name):
    return listSeries.apply(lambda x: name in x)

all_categories = getListOfCategories(product_data)
category_weight_list = [category_weights[all_categories[i]] for i in range(len(all_categories))]

def getProductHotness(index, products, all_categories, category_weights):
    product_evaluated = products.loc[index]
    interesting_categories = [category for category in all_categories if product_evaluated[category]]
    score = 0
    for category in interesting_categories:
        matching_products = products.loc[(products.index != index) & (products[category] == True)]
        if not matching_products.empty:
            score += (matching_products.price - product_evaluated.price).mean() * category_weights[category]
    return score

def preprocess_products(products, all_categories, category_weights):
    for category in all_categories:
        newSeries = categoryListIntoSeries(products.category_path, category)
        products[category] = newSeries
    grp = products.groupby(all_categories)
    for line in sorted([group['category_path'].iloc[0] for name, group in grp]): 
        print(line)
    
    products['hotness'] = np.nan
    getProductHotness(1001, products, all_categories, category_weights)
    for index in products.index:
        products.loc[index, 'hotness'] = getProductHotness(index, products, all_categories, category_weights)


preprocess_products(product_data, all_categories, category_weights)

groupped_sessions = session_data.groupby('session_id')


def getSessionAttributes(session, products):
    s_id = session['session_id'].unique()[0]

    timestamps = session.iloc[[0, -1]].timestamp.values
    duration = (timestamps[1] - timestamps[0]) / np.timedelta64(1, 's')

    event = session.iloc[-1].event_type
    isSuccessfull = True if event == 'BUY_PRODUCT' else False

    discount = session['offered_discount'].values

    product_ids = group['product_id']
    viewed_products_data = products.loc[product_ids, ['product_name', 'price']]
    viewed_products_data.insert(1, 'offered_discount', discount, True)
    viewed_products_data.insert(2, 'discount_value',
                                viewed_products_data.price * viewed_products_data.offered_discount, True)

    mean_values = viewed_products_data.mean()

    avg_price = mean_values.price
    avg_discount_percent = mean_values.offered_discount
    avg_discount_value = mean_values.discount_value

    sum_values = viewed_products_data.sum()
    total_discount_percent = sum_values.offered_discount
    total_discount_value = sum_values.discount_value

    result = {
        'id': s_id,
        'duration': duration,
        'avg_price': avg_price,
        'avg_discount_percent': avg_discount_percent,
        'total_discount_percent': total_discount_percent,
        'avg_discount_value': avg_discount_value,
        'total_discount_value': total_discount_value,
        'success': isSuccessfull
    }
    return result


data = []
for name, group in groupped_sessions:
    data.append(getSessionAttributes(group, product_data))

sessiondf = pd.DataFrame(data)
sessiondf.set_index('id', inplace=True)


def simplifyColumn(df, column):
    df.loc[df[column] > 0, column] = df.loc[df[column] > 0, column].apply(np.log10).apply(np.floor)


sessiondf_p = sessiondf.copy()
for column in sessiondf_p.columns[:-1]:
    simplifyColumn(sessiondf_p, column)

grouped_p = sessiondf_p.groupby(
    ['duration', 'avg_price', 'avg_discount_percent', 'total_discount_percent', 'avg_discount_value',
     'total_discount_value'])

sessiondf['probability'] = np.nan

for name, group in grouped_p:
    result = group['success'].sum() / len(group)
    sessiondf.loc[group.index, 'probability'] = result
    print(name, result)

sessiondf.drop(inplace=True, columns=['success'])

corr = sessiondf.corr()

mask = np.zeros_like(corr, dtype=np.bool)
mask[np.triu_indices_from(mask)] = True

fig = plt.figure(figsize=(12, 8))
sns.heatmap(corr, mask=mask, vmax=.3, center=0,
            square=True, linewidths=.5, cbar_kws={"shrink": .5})

sessiondf.to_csv(path_or_buf='session_preprocessed.csv')