import mysql.connector
# from .some_module import get_gain
from datetime import datetime, timedelta
from typing import List, Tuple
DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'wealthwise',
    'raise_on_warnings': True
}

def set_custom_notification(request, message_text, message_type='success'):
    """
    Stocke un message de notification personnalisé (flash) dans la session 
    pour un affichage en pop-up après redirection.
    """
    if 'custom_notifications' not in request.session:
        request.session['custom_notifications'] = []
    
    request.session['custom_notifications'].append({
        'type': message_type,
        'text': message_text
    })

    request.session.modified = True

def connection():
    """Function to connect to the database."""
    try:
        con = mysql.connector.connect(**DB_CONFIG)
        return con
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        raise Exception(f"Database connection failed: {err}")
def get_achat_for_processing() -> List[Tuple]:
    """
    Récupère les achats qui sont dus MAINTENANT et qui n'ont pas expiré.
    Retourne une liste de lignes d'achat (tuples).
    """
    con = connection()
    cursor = con.cursor()
    sql = """
        SELECT codeAchat, codeClt, codePack, prochain_revenu_du, cycles_restants
        FROM achat 
        WHERE prochain_revenu_du <= NOW() AND cycles_restants > 0
    """
    
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error executing query for due purchases: {err}")
        results = []
    finally:
        cursor.close()
        con.close()
        
    return results
def update_achat_cycle(achat_id: int, cycles_restants_actuel: int, prochain_revenu_du_actuel: datetime) -> bool:
    """
    Décrémente le compteur de cycle et décale le prochain paiement de 24 heures.
    """
    if cycles_restants_actuel <= 0:
        return False
    nouveau_cycle = cycles_restants_actuel - 1
    nouveau_prochain_paiement = prochain_revenu_du_actuel + timedelta(hours=24)
    
    con = connection()
    cursor = con.cursor()
    sql = """
        UPDATE achat 
        SET cycles_restants = %s, prochain_revenu_du = %s 
        WHERE codeAchat = %s
    """
    
    try:
        cursor.execute(sql, (nouveau_cycle, nouveau_prochain_paiement, achat_id))
        con.commit()
        success = True
    except mysql.connector.Error as err:
        print(f"Error executing cycle update for achat ID {achat_id}: {err}")
        con.rollback()
        success = False
    finally:
        cursor.close()
        con.close()
        
    return success
def process_incrementation():
    """
    Logique principale qui crédite le revenu et met à jour les cycles des packs dus.
    """
    achats_dus = get_achat_for_processing()
    
    packs_credites_count = 0
    for achat in achats_dus:
        achat_id = achat[0]
        client_id = achat[1]
        pack_code = achat[2]
        prochain_revenu_du = achat[3]
        cycles_restants = achat[4]
        revenue_amount = get_gain(pack_code)
        
        if revenue_amount > 0 and cycles_restants > 0:
            success_increment = increment_solde(revenue_amount, client_id)
            
            if success_increment:
                success_update = update_achat_cycle(achat_id, cycles_restants, prochain_revenu_du)
                
                if success_update:
                    packs_credites_count += 1
                else:
                    print(f"Erreur critique: Échec de la mise à jour du cycle pour Achat ID {achat_id} après crédit client.")
            else:
                print(f"Failed to increment revenue for client ID: {client_id}")

    print(f"Client revenue incrementation process complete. {packs_credites_count} cycles crédités.")
def delete_old_purchases(days_since_expiration: int = 10) -> bool:
    """
    Supprime les achats dont tous les cycles de revenus sont terminés.
    On peut ajouter un délai (ex: 10 jours après expiration, cycles_restants=0) pour l'historique.
    """
    con = connection()
    cursor = con.cursor()
    sql = 'DELETE FROM achat WHERE cycles_restants <= 0'
    
    try:
        cursor.execute(sql) 
        con.commit()
        print(f"Deleted {cursor.rowcount} expired purchase records (cycles_restants <= 0).")
        success = True
    except mysql.connector.Error as err:
        print(f"Error executing deletion of expired packs: {err}")
        con.rollback()
        success = False
    finally:
        cursor.close()
        con.close()
        
    return success
if __name__ == '__main__':
    print("--- Executing Revenue Incrementation ---")
    process_incrementation()

    print("\n--- Executing Expired Purchase Deletion ---")
    delete_old_purchases()