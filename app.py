from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import Response, JSONResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import or_, not_, and_, select, asc, desc
from auth import authenticate_user, get_current_user, get_hashed_password, AuthenticationException
from services import createDatabase, get_db
from models import User, Group, GroupMember, Expense, ExpenseSplit, Settlement, Friends, FriendRequests
from auth import get_user
import os
import traceback
from pydantic import BaseModel, EmailStr
from collections import defaultdict
from datetime import datetime

dir_path = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=f"{dir_path}/templates")

app = FastAPI()

createDatabase()

app.mount("/static", StaticFiles(directory=f"{dir_path}/static"), name="static")

@app.exception_handler(AuthenticationException)
async def authentication_exception_handler(request: Request, exc: AuthenticationException):
    return RedirectResponse(url="/login")  # Redirect to the login page if the user is not authenticated


@app.get("/login")
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", context={"request": request})

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/login")
async def login(request: LoginRequest, response: Response):
    try:
        email = request.email.lower()
        password = request.password
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to login. {str(e)}"
        )
    
    user = authenticate_user(email, password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Not Authenticated."
        )
    elif not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect Password."
        )
    
    response = JSONResponse(content={"redirect_url": "/"})
    response.set_cookie(key="email", value=user.get("email"), httponly=True)

    return response

@app.get("/register")
async def get_register(request: Request):
    return templates.TemplateResponse("register.html", context={"request": request})

@app.post("/register")
async def register(request: Request, response: Response, db:Session=Depends(get_db)):
    try:
        form_data = await request.form()

        first_name = form_data.get("first_name")
        last_name = form_data.get("last_name")
        email = form_data.get("email")
        phone_number = form_data.get("phone_number")
        password = form_data.get("password")
        role = "admin"
        
        if get_user(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists."
            )
        
        hashed_passsword = get_hashed_password(password)

        new_user = User()
        new_user.email = email.lower()
        new_user.first_name = first_name.title()
        new_user.last_name = last_name.title()
        new_user.password = hashed_passsword
        new_user.phone_number = phone_number
        new_user.role = role

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return response
    except Exception as e:
        traceback.print_exc()

@app.get("/")
async def get_groups(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    group_list = (
        db.query(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .filter(GroupMember.user_id == current_user.get("user_id"))
        .all()
    )
    
    return templates.TemplateResponse('groups.html', context={'request': request, 'total_owe': 0, 'group_list': group_list})

@app.get("/friends")
async def get_friends(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    # Fetch the friends
    friend_list = (
        db.query(User)
        .join(Friends, Friends.friend_id == User.id)
        .filter(Friends.user_id == current_user.get("user_id"))
        .all()
    )

    return templates.TemplateResponse('friends.html', context={'request': request, 'friend_list': friend_list})

@app.get("/friend-requests")
async def get_friend_requests(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    friend_request_list = (
        db.query(FriendRequests.friend_request_id, User.first_name, User.last_name)
        .join(FriendRequests, FriendRequests.friend_request_id == User.id)
        .filter(FriendRequests.user_id == current_user.get("user_id"))
        .all()
    )

    return templates.TemplateResponse('friend-requests.html', context={'request': request, 'total_friend_requests': len(friend_request_list), 'friend_list': friend_request_list})

@app.get("/search-friend")
async def get_add_friend(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    return templates.TemplateResponse('search-friend.html', context={'request': request, 'friend_list': []})

@app.post("/search-friend")
async def search_friends(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    form_data = await request.form()
    search_name = form_data.get("search_friend")
    
    # Get a list of user IDs who are already friends with the current user
    existing_friend_ids = select(Friends.friend_id).where(Friends.user_id == current_user.get("user_id"))


    # Query to find users matching the search term, excluding the current user and existing friends
    users = db.query(User).filter(
        or_(
            User.first_name.ilike(f"%{search_name}%"),
            User.last_name.ilike(f"%{search_name}%")
        ),
        not_(User.id.in_(existing_friend_ids)),  # Exclude existing friends
        User.id != current_user.get("user_id")              # Exclude current user
    ).all()

    return templates.TemplateResponse('search-friend.html', context={'request': request, 'data_list': users})

@app.get("/add-group")
async def get_add_group(request: Request, current_user= Depends(get_current_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse('add-group.html', context={'request': request})

@app.post("/add-group")
async def add_group(request: Request, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    form_data = await request.form()

    group_name = form_data.get("group_name")

    existing_groups = db.query(Group).filter(Group.name == group_name).all()

    if not existing_groups:
        # Add the new group
        new_group = Group(name=group_name.strip())  # Strip whitespace
        db.add(new_group)
        db.commit()
        db.refresh(new_group)

        # Add the current user as a group member
        new_group_member = GroupMember(group_id=new_group.id, user_id=current_user.get("user_id"))
        db.add(new_group_member)
        db.commit()
        db.refresh(new_group_member)
    else:
        new_group = existing_groups[0]  # If group already exists, use it

        # Optionally, you can check if the user is already in the group before adding
        existing_member = (
            db.query(GroupMember)
            .filter(GroupMember.group_id == new_group.id, GroupMember.user_id == current_user.get("user_id"))
            .first()
        )
        if not existing_member:
            new_group_member = GroupMember(group_id=new_group.id, user_id=current_user.get("user_id"))
            db.add(new_group_member)
            db.commit()
            db.refresh(new_group_member)

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.get("/view-group/{group_id}")
async def get_view_group(request: Request, group_id: str, current_user= Depends(get_current_user), db: Session = Depends(get_db)):
    
    result = db.query(
        Expense.expense_id, Expense.group_id, Expense.description, Expense.amount,
        Expense.paid_by, Expense.split_type, Expense.created_by, User.first_name, User.last_name,
        ExpenseSplit.share, Expense.created_at
    ).join(
        ExpenseSplit, ExpenseSplit.expense_id == Expense.expense_id
    ).join(
        User, Expense.paid_by == User.id
    ).filter(
        and_(
            Expense.group_id == group_id,
            ExpenseSplit.user_id != current_user.get("user_id")
        )
    ).order_by(
        desc(Expense.created_at)
    ).all()

    grouped_data = defaultdict(list)

    # Process each transaction in the result
    for row in result:
        # Extract the relevant fields
        expense_id = row.expense_id
        group_id = row.group_id
        description = row.description
        amount = row.amount
        paid_by = row.paid_by
        payee_first_name = row.first_name
        payee_last_name = row.last_name[0].upper() + " " if row.last_name else ""
        split_type = row.split_type
        created_by = row.created_by
        share = row.share
        created_at = row.created_at

        # Extract month and year for grouping
        month_key = created_at.strftime("%B %Y")

        create_date = created_at.strftime("%b %d")

        # Determine transaction type (lent or owe)
        transaction_type = "tumne lene hai" if paid_by == current_user.get("user_id")  else "tumne dene hai"

        amount_paid_by = payee_first_name.title() + " " + payee_last_name + "paid ₹" + str(amount) if paid_by != current_user.get("user_id")  else "You paid ₹" + str(amount)

        # Add the transaction to the grouped data
        grouped_data[month_key].append({
            "group_id": group_id,
            "expense_id": expense_id,
            "transaction_date": create_date if len(create_date) > 1 else f"0{create_date}",
            "description": description,
            "amount_paid_by": amount_paid_by,
            "transaction_type": transaction_type,
            "share": f"₹ {str(share)}"
        })

    return templates.TemplateResponse('view-group.html', context={'request': request, "group_id": group_id, "data_list": grouped_data})

@app.get("/add-expense/{group_id}")
async def get_add_expense(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    group_details = (
        db.query(Group.id, Group.name, User.first_name, User.last_name, GroupMember.user_id)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .join(User, User.id == GroupMember.user_id)
        .filter(Group.id == group_id)
        .all()
    )

    return templates.TemplateResponse('add-expense.html', context={'request': request, "current_user": current_user, "group_id": group_id, "group_members": group_details})

@app.post("/add-expense/{group_id}")
async def add_expense(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    form_data = await request.form()

    expense_description = form_data.get("expense_description")
    expense_amount = float(form_data.get("expense_amount")) if form_data.get("expense_amount") else 0
    expense_paid_by = form_data.get("expense_paid_by")
    expense_split_amoung = form_data.getlist("expense_split_amoung[]")
    expense_split_type = form_data.get("split_type")
    expense_date = form_data.get("expense_date")
    expense_ratios = form_data.getlist("expense_ratios")
    current_user_id = current_user.get("user_id")

    if expense_date:
        try:
            expense_date = datetime.strptime(expense_date, "%Y-%m-%dT%H:%M")
        except ValueError:
            return {"error": "Invalid date format. Please use the correct format."}
    
        new_expense = Expense(
            group_id = group_id,
            description = expense_description,
            amount = expense_amount,
            paid_by = expense_paid_by,
            split_type = expense_split_type,
            created_by = current_user_id,
            created_at = expense_date
        )
    else:
        new_expense = Expense(
            group_id = group_id,
            description = expense_description,
            amount = expense_amount,
            paid_by = expense_paid_by,
            split_type = expense_split_type,
            created_by = current_user_id
        )
    db.add(new_expense)
    db.commit()

    if not expense_split_amoung:

        group_member_ids = [group_member.user_id for group_member in db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()]
        print(group_member_ids)
        for member in group_member_ids:
            member_share = 0
            if expense_split_type == "equal":
                print("added expense for user id", member)
                member_share = expense_amount / len(group_member_ids)
                new_expense_split = ExpenseSplit(
                    expense_id = new_expense.expense_id,
                    user_id = int(member),
                    share = member_share,
                    ratio = 0
                )
                db.add(new_expense_split)
                db.commit()
        
        response = RedirectResponse(url=f"/view-group/{group_id}", status_code=status.HTTP_303_SEE_OTHER)
        return response

    for member in expense_split_amoung:
        member_share = 0
        if expense_split_type == "equal":
            print("adding expense for user id", member)
            member_share = expense_amount / len(expense_split_amoung)
            new_expense_split = ExpenseSplit(
                expense_id = new_expense.expense_id,
                user_id = int(member),
                share = member_share,
                ratio = 0
            )
            db.add(new_expense_split)
            db.commit()

    response = RedirectResponse(url=f"/view-group/{group_id}", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.get("/add-member/{group_id}")
async def get_add_meber(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    # Get all friend user IDs as a flat list
    group_members_ids = [group_member.user_id for group_member in db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()]

    # Query to get friends in the group who are not already in all_friends
    friends_list = (
        db.query(Friends.friend_id, User.first_name, User.last_name)
        .join(Friends, Friends.friend_id == User.id)
        .filter(
            Friends.friend_id.not_in(group_members_ids)
        )
        .all()
    )

    return templates.TemplateResponse('add-member.html', context={'request': request, "current_user": current_user, "group_id": group_id, "friends": friends_list})

@app.post("/add-member/{group_id}")
async def add_expense(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    form_data = await request.form()

    for member_id in form_data.get("members"):
        new_member = GroupMember(
            group_id = group_id,
            user_id = member_id
        )

        db.add(new_member)
        db.commit()
        db.refresh(new_member)

    response = RedirectResponse(url=f"/view-group/{group_id}", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.post("/send-friend-request/{friend_request_id}")
async def send_friend_request(request: Request, friend_request_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    new_friend_request = FriendRequests(
        friend_request_id = current_user.get("user_id"),
        user_id = friend_request_id
    )

    db.add(new_friend_request)
    db.commit()
    db.refresh(new_friend_request)

    response = RedirectResponse(url=f"/search-friend", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.post("/accept-friend-request/{friend_request_id}")
async def accept_friend_request(request: Request, friend_request_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    new_friend = Friends(
        friend_id = friend_request_id,
        user_id = current_user.get("user_id")
    )

    db.add(new_friend)
    db.commit()
    db.refresh(new_friend)

    friend = Friends(
        friend_id = current_user.get("user_id"),
        user_id = friend_request_id
    )

    db.add(friend)
    db.commit()
    db.refresh(friend)

    # Remove friend request
    db.query(FriendRequests).filter(FriendRequests.friend_request_id == friend_request_id).delete()
    db.commit()

    response = RedirectResponse(url=f"/friends", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.post("/reject-friend-request/{friend_request_id}")
async def reject_friend_request(request: Request, friend_request_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    # Remove friend request
    db.query(FriendRequests).filter(FriendRequests.friend_request_id == friend_request_id).delete()
    db.commit()

    response = RedirectResponse(url=f"/friends", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.get("/leave-group/{group_id}")
async def leave_group(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    # Remove friend request
    db.query(GroupMember).filter(
        and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.get("user_id")
        )
    ).delete()
    db.commit()

    response = RedirectResponse(url=f"/", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.get("/delete-expense/{group_id}/{expense_id}")
async def delete_expense(request: Request, group_id: int, expense_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    db.query(ExpenseSplit).filter(
        ExpenseSplit.expense_id == expense_id
    ).delete()
    db.commit()

    db.query(Expense).filter(
        Expense.expense_id == expense_id
    ).delete()
    db.commit()

    response = RedirectResponse(url=f"/view-group/{group_id}", status_code=status.HTTP_303_SEE_OTHER)
    return response