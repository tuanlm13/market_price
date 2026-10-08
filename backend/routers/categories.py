import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas, auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def get_categories(
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_optional_current_user),
):
    if scope == "market" or current_user is None:
        from app.taxonomy.models import DimCategory
        return db.query(DimCategory).order_by(DimCategory.name).all()
    if current_user.is_admin:
        return db.query(models.Category).order_by(models.Category.name).all()
    return (
        db.query(models.Category)
        .filter(models.Category.user_id == current_user.id)
        .order_by(models.Category.name)
        .all()
    )


@router.post("", response_model=schemas.CategoryOut)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    existing = (
        db.query(models.Category)
        .filter(
            models.Category.user_id == current_user.id,
            models.Category.name == category.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    new_cat = models.Category(
        user_id=current_user.id, name=category.name, color=category.color
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


@router.patch("/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: int,
    updates: schemas.CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if not current_user.is_admin and cat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(cat, key, value)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if not current_user.is_admin and cat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    db.delete(cat)
    db.commit()
    return {"message": "Category deleted"}


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def set_product_categories(
    product_id: int,
    body: schemas.ProductCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not current_user.is_admin and product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorised")
    categories = (
        db.query(models.Category)
        .filter(models.Category.id.in_(body.category_ids))
        .all()
    )
    product.categories = categories
    db.commit()
    db.refresh(product)
    return product
