#language-learning/src/grammar_learner/clustering.py 0.5 80726+80802
import numpy as np
import pandas as pd
from utl import UTC

def cluster_words_kmeans(words_df, n_clusters, init='k-means++', n_init=10):
    # words_df - pandas DataFrame
    # n_init -
    # inint: 'k-means++', 'random', ndarray? - TODO: check docs
    from sklearn.cluster import KMeans
    from sklearn.metrics import pairwise_distances, silhouette_score
    words_list = words_df['word'].tolist()
    df = words_df.copy()
    del df['word']
    #-fails? = KMeans(init='random', n_clusters=n_clusters, n_init=30)   #80617 #F?!
    #-kmeans_model = KMeans(init='k-means++', n_clusters=n_clusters, n_init=10)
    kmeans_model = KMeans(init=init, n_clusters=n_clusters, n_init=n_init)
    kmeans_model.fit(df)
    #-print('cluster_words_kmeans: kmeans_model.fit(df)')
    labels = kmeans_model.labels_
    inertia  = kmeans_model.inertia_
    centroids = np.asarray(kmeans_model.cluster_centers_[:(max(labels)+1)])
    silhouette = silhouette_score(df, labels, metric ='euclidean')

    cdf = pd.DataFrame(centroids)
    cdf = cdf.applymap(lambda x: x if abs(x) > 1e-12 else 0.)
    cdf.columns = [x+1 if type(x)==int else x for x in cdf.columns]
    cols = cdf.columns.tolist()
    def cluster_word_list(i):
        return [words_list[j] for j,x in enumerate(labels) if x==i]
    cdf['cluster'] = cdf.index
    cdf['cluster_words'] = cdf['cluster'].apply(cluster_word_list)
    #+cdf = cdf.sort_values(by=[1,2,3], ascending=[True,True,True])
    cdf = cdf.sort_values(by=[1,2], ascending=[True,True])
    cdf.index = range(1, len(cdf)+1)
    def cluster_id(row): return 'C' + str(row.name).zfill(2)
    cdf['cluster'] = cdf.apply(cluster_id, axis=1)
    cols = ['cluster', 'cluster_words'] + cols
    cdf = cdf[cols]

    return cdf, silhouette, inertia


def number_of_clusters(vdf, cluster_range, algorithm='kmeans', \
        criteria='silhouette', level=0.9, verbose='none'):
    from statistics import mode
    from utl import round1, round2, round3

    if(len(cluster_range) < 2 or cluster_range[2] < 1):
        print('number_of_clusters: range:', cluster_range)
        return cluster_range[0]

    sil_range = pd.DataFrame(columns=['Np','Nc','Silhouette','Inertia'])
    if verbose == 'debug':
        print('clustering/poc.py/number_of_clusters: vdf:\n', \
            vdf.applymap(round2).sort_values(by=[1,2], ascending=[True,True]))

    # Check number of clusters <= word vector dimensionality
    max_clusters = min(cluster_range[1], len(vdf), \
                       max([x for x in list(vdf) if isinstance(x,int)]))
    #?if max([x for x in list(vdf) if isinstance(x,int)]) < cluster_range[0]+1:
    #?    max_clusters = min(cluster_range[1], len(vdf))  #FIXME: hack 80420!
    if max([x for x in list(vdf) if isinstance(x,int)]) == 2:
        if verbose in ['max','debug']: print('2 dim word space -- 4 clusters')
        return 4  #FIXME: hack 80420!

    if verbose in ['max', 'debug']:
        print('number_of_clusters: max_clusters =', max_clusters)
    n_clusters = max_clusters   #80623: cure case max < range.min

    #FIXME: unstable number of clusters #80422
    lst = []
    attempts = 1 #12
    for k in range(attempts):
        for i,j in enumerate(range(cluster_range[0], max_clusters, cluster_range[2])):
            cdf, silhouette, inertia = cluster_words_kmeans(vdf, j)
            if verbose in ['debug']:
                print(j, 'clusters ⇒ silhouette =', silhouette)
            sil_range.loc[i] = [j, len(cdf), round(silhouette,4), round(inertia,2)]
            if level > 0.9999:   # 1 - max Silhouette index
                n_clusters = sil_range.loc[sil_range['Silhouette'].idxmax()]['Nc']
            elif level < 0.0001: # 0 - max number of clusters
                n_clusters = sil_range.loc[sil_range['Nc'].idxmax()]['Nc']
            else:
                thresh = level * sil_range.loc[sil_range['Silhouette'].idxmax()]['Silhouette']
                n_clusters = min(sil_range.loc[sil_range['Silhouette'] > thresh]['Nc'].tolist())
        lst.append(int(n_clusters))

    dct = dict()
    for n in lst:
        if n in dct:
            dct[n] += 1
        else: dct[n] = 1
    n_clusters = int(round(np.mean(lst),0))
    n2 = list(dct.keys())[list(dct.values()).index(max(list(dct.values())))]
    if n2 != n_clusters:
        if len(list(dct.values())) == len(set(list(dct.values()))):
            n3 = mode(lst)  # Might get error
        else: n3 = n_clusters
        n_clusters = int(round((n_clusters + n2 + n3)/3.0, 0))

    if verbose in ['max', 'debug']:
        if len(dct) > 1:
            print('Clusters:', sorted(lst), '⇒', n_clusters)
    return int(n_clusters)

#80803 TODO: replace number_of_clusters

def best_clusters(vdf, **kwargs):
    print('best_clusters')
    def kwa(v,k): return kwargs[k] if k in kwargs else v
    #-cluster_range = kwa((2,48,1), 'cluster_range')
    crange      = kwa((2,48,3),     'cluster_range')
    algo        = kwa('kmeans',     'clustering')
    criteria    = kwa('silhouette', 'cluster_criteria')
    level       = kwa(0.9,          'cluster_level')
    verbose     = kwa('none',       'verbose')

    if type(algo) is str:
        if algo == 'kmeans':
            algorithm = 'kmeans'
            init = 'k-means++'
            n_init = 10
    elif type(algo) is tuple:
        if algo[0] == 'kmeans':
            algorithm = 'kmeans'
            if len(algo) > 1:
                if algo[1][0] == 'r':
                    init = 'random'
                else: init = 'k-means++'
            else: init = 'k-means++'
            if len(algo) > 2:
                try: n_init = int(algo[2])
                except: n_init = 10
            else: n_init = 10

    from operator import itemgetter
    from utl import round1, round2, round3

    if (len(crange)<2 or crange[1]<=crange[0] or crange[2]==0):  #fixed n_clusters
        if verbose in ['max','debug']:
            print(UTC(),':: best_clusters: max clusters in range', crange)
        clusters, silhouette, inertia = cluster_words_kmeans(vdf, crange[0])
        return clusters, silhouette, inertia

    #-elif False:  #80803 DONE: FIXME:DEL
    #-    n_clusters = number_of_clusters( \
    #-        vdf, crange, algorithm, criteria, level, verbose)
    #-    clusters, silhouette, inertia = cluster_words_kmeans(vdf, n_clusters)
    #-    return clusters, silhouette, inertia    #80803 v.0.1
        #80803 ~OK
    else:   #TODO: elif algorithm == 'kmeans'
        # Check number of clusters <= word vector dimensionality
        max_clusters = min(crange[1], len(vdf), \
                           max([x for x in list(vdf) if isinstance(x,int)]))
        if max([x for x in list(vdf) if isinstance(x,int)]) == 2:
            max_clusters = 4    #FIXME: hack 80420: 2D word space ⇒ 4 clusters
        c = pd.DataFrame(columns=['cluster','cluster_words'])
        s = 0
        i = 0
        while max_clusters > crange[0]:
            try:
                c,s,i = cluster_words_kmeans(vdf, max_clusters, init, n_init)
                break
            except: max_clusters -= 1
        if verbose in ['max', 'debug']:
            print(UTC(),':: best_clusters: max_clusters =', max_clusters)
        n_clusters = max_clusters   #80623: cure case max < crange.min

        if level < 0.1: return c,s,i    #return max possible number of clusters

        else:
            lst = []
            lst.append((0, max_clusters, c,s,i))
            min_clusters = crange[0]
            while min_clusters < max_clusters:
                try:
                    c,s,i = cluster_words_kmeans(vdf, min_clusters, init, n_init)
                    break
                except: min_clusters += 1
            if verbose in ['max', 'debug']:
                print(UTC(),':: best_clusters: min_clusters =', min_clusters)
            lst.append((1, min_clusters, c,s,i))
            middle = int((min_clusters + max_clusters)/2)
            c,s,i = cluster_words_kmeans(vdf, middle, init, n_init)
            lst.append((2, middle, c,s,i))
            if verbose in ['debug']:
                print('\nstarting lst:')
                for x in lst: print([x[i] for i in [0,1,3,4]])
            lst.sort(key=itemgetter(3), reverse=True)

            ntop = 1
            while ntop < crange[2]:
                no = lst[0][1]
                c,s,i = cluster_words_kmeans(vdf, no, init, n_init)
                lst.append((len(lst), no, c,s,i))
                dn = int(round(0.6*abs(no - lst[ntop][1]), 0))
                if ntop > crange[2]/2.0:
                    dn = 1
                if no > min_clusters:
                    nm = max(no - dn, min_clusters)
                    c,s,i = cluster_words_kmeans(vdf, nm, init, n_init)
                    lst.append((len(lst), nm, c,s,i))
                if no < max_clusters:
                    nm = min(no + dn, max_clusters)
                    c,s,i = cluster_words_kmeans(vdf, nm, init, n_init)
                    lst.append((len(lst), nm, c,s,i))
                lst.sort(key=itemgetter(3), reverse=True)
                for i,x in enumerate(lst):
                    ntop = i+1
                    if x[1] != lst[i+1][1]: break

            n_clusters = lst[0][1]
            clusters = lst[0][2]
            silhouette = lst[0][3]
            inertia = lst[0][4]

            if verbose in ['max','debug']:
                print(UTC(),':: best_clusters: return', n_clusters, 'clusters')
            if verbose in ['debug']:
                print(clusters.applymap(round1))
            if verbose in ['max','debug']:
                print('\ntop clusters: test_no, n_clusters, silhouette, inertia')
                for x in lst: print([x[i] for i in [0,1,3,4]])

            return clusters, silhouette, inertia

def group_links(links, verbose):  #80428    #80802 moved here
    # Group identical Lexical Entries (ILE) #80428
    import pandas as pd
    df = links.copy()
    df['links'] = [[x] for x in df['link']]
    del df['link']
    if verbose in ['max','debug']:
        print('\ngroup_links: links:\n')
        with pd.option_context('display.max_rows', 6):
            print(links.sort_values(by='word', ascending=True))
        print('\ngroup_links: df:\n')
        with pd.option_context('display.max_rows', 6): print(df)
    df = df.groupby('word').agg({'links': 'sum', 'count': 'sum'}).reset_index()
    df['words'] = [[x] for x in df['word']]
    del df['word']
    df2 = df.copy().reset_index()
    df2['links'] = df2['links'].apply(lambda x: tuple(sorted(x)))
    df3 = df2.groupby('links')['count'].apply(sum).reset_index()
    if verbose == 'debug':
        with pd.option_context('display.max_rows', 6): print('\ndf3:\n', df3)
    df4 = df2.groupby('links')['words'].apply(sum).reset_index()
    if df4['links'].tolist() == df3['links'].tolist():
        df4['counts'] = df3['count']
    else: print('group_links: line 30 if df4... == df3... ERROR!')
    df4['words'] = df4['words'].apply(lambda x: sorted(list(x)))
    df4['links'] = df4['links'].apply(lambda x: sorted(list(x)))
    df4 = df4[['words','links','counts']].sort_values(by='words', ascending=True)
    df4.index = range(1, len(df4)+1)
    def cluster_id(row): return 'C' + str(row.name).zfill(2)
    df4['cluster'] = df4.apply(cluster_id, axis=1)
    df4 = df4.rename(columns={'words': 'cluster_words', 'links': 'disjuncts'})
    df4 = df4[['cluster', 'cluster_words', 'disjuncts', 'counts']]
    return df4


#Notes:

#80617 kmeans_model = KMeans(init='random', n_clusters=n_clusters, n_init=30)   #fails?
#80725 POC 0.1-0.4 deleted, 0.5 restructured. This module was src/clustering/poc05.py
#80802 poc05 restructured,
    #cluster_words_kmeans moved here (from kmeans.py) for further dev
    #number_of_clusters copied to kmeans.py: tmp poc05 "stable" baseline
    #group_links moved here from category_learner.py
    #clusters2list, clusters2dict removed
#TODO: n_clusters ⇒ best_clusters: return best clusters (word lists), centroids
