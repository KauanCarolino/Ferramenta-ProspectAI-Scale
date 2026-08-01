"""Pacote do serviço de leads."""

from services.leads.service import create_lead, delete_lead, get_lead, list_leads, update_lead

__all__ = ["create_lead", "delete_lead", "get_lead", "list_leads", "update_lead"]
