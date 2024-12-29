from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import Response, JSONResponse, RedirectResponse, StreamingResponse
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
from sqlalchemy.orm import Session, aliased
from sqlalchemy import or_, not_, and_, select, asc, desc, func
from auth import authenticate_user, get_current_user, get_hashed_password, AuthenticationException, UserNotFoundException
from services import createDatabase, get_db
from models import User, Group, GroupMember, Expense, ExpenseSplit, Settlement, Friends, FriendRequests
from auth import get_user
import os
import traceback
from pydantic import BaseModel, EmailStr
from collections import defaultdict
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from io import BytesIO

dir_path = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=f"{dir_path}/templates")

app = FastAPI()

createDatabase()

app.mount("/static", StaticFiles(directory=f"{dir_path}/static"), name="static")

@app.exception_handler(AuthenticationException)
async def authentication_exception_handler(request: Request, exc: AuthenticationException):
    return RedirectResponse(url="/login")  # Redirect to the login page if the user is not authenticated

@app.exception_handler(UserNotFoundException)
async def user_not_found_exception_handler(request: Request, exc: UserNotFoundException):
    return RedirectResponse(url="/register") # Redirect to the register page if the user is not found


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
    response.set_cookie(key="email", value=user.get("email"), path="/", httponly=True)

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

@app.get("/reset-password/{user_id}")
async def reset_password_request(
    request: Request, user_id: int, db: Session = Depends(get_db)
):
    # Check if the user exists
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundException

    user.password = get_hashed_password("User@123")
    db.commit()

    return {"message": "Password reset successfully."}

@app.post("/logout")
async def logout(request: Request, response: Response):
    try:
        response.delete_cookie(key="email", path="/")
        
        # Optionally, you can redirect or return a message
        return RedirectResponse(
            url="/login",
            status_code=303
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during logout. {str(e)}"
        )
    
@app.get("/")
async def get_groups(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    group_list = (
        db.query(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .filter(GroupMember.user_id == current_user.get("user_id"))
        .all()
    )

    friend_request_list = (
        db.query(FriendRequests.friend_request_id, User.first_name, User.last_name)
        .join(FriendRequests, FriendRequests.friend_request_id == User.id)
        .filter(FriendRequests.user_id == current_user.get("user_id"))
        .all()
    )
    
    return templates.TemplateResponse('groups.html', context={'request': request, 'total_owe': 0, 'group_list': group_list, 'total_friend_requests': len(friend_request_list)})

@app.get("/friends")
async def get_friends(request: Request, current_user= Depends(get_current_user),  db:Session = Depends(get_db)):

    # Fetch the friends
    friend_list = (
        db.query(User)
        .join(Friends, Friends.friend_id == User.id)
        .filter(Friends.user_id == current_user.get("user_id"))
        .all()
    )

    friend_request_list = (
        db.query(FriendRequests.friend_request_id, User.first_name, User.last_name)
        .join(FriendRequests, FriendRequests.friend_request_id == User.id)
        .filter(FriendRequests.user_id == current_user.get("user_id"))
        .all()
    )

    return templates.TemplateResponse('friends.html', context={'request': request, 'friend_list': friend_list, 'total_friend_requests': len(friend_request_list)})

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
async def get_view_group(request: Request, group_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):

    user_alias = aliased(User, name="expense_split_user")

    # Check if the current user has any entries in the ExpenseSplit table for the given group
    user_expense_splits = db.query(ExpenseSplit).join(Expense).filter(
        Expense.group_id == group_id,
        ExpenseSplit.user_id == int(current_user.get("user_id"))
    ).all()

    # If no records found in ExpenseSplit for the current user, return blank data
    if not user_expense_splits:
        return templates.TemplateResponse('view-group.html', context={'request': request, "group_id": group_id, "data_list": {}, "total_paid_by_user": 0})


    result = db.query(
        Expense.expense_id.label("expense_id"), 
        Expense.group_id.label("group_id"), 
        Expense.description.label("description"), 
        Expense.amount.label("amount"),
        Expense.paid_by.label("paid_by"), 
        Expense.split_type.label("split_type"), 
        Expense.created_by.label("created_by"), 
        User.first_name.label("paid_by_first_name"),
        User.last_name.label("paid_by_last_name"),
        ExpenseSplit.share.label("share"),
        Expense.created_at.label("created_at"),
        user_alias.id,
        user_alias.first_name.label("expense_split_first_name"),
        user_alias.last_name.label("expense_split_last_name")
    ).join(
        ExpenseSplit, ExpenseSplit.expense_id == Expense.expense_id
    ).join(
        User, Expense.paid_by == User.id
    ).join(
        user_alias, ExpenseSplit.user_id == user_alias.id
    ).filter(
        Expense.group_id == group_id
    ).order_by(
        desc(Expense.created_at)
    ).all()

    # Fetch the total amount paid by the current user in settlements
    total_paid_by_user = db.query(
        func.sum(Settlement.amount).label("total_paid")
    ).filter(
        and_(
            Settlement.payer_id == int(current_user.get("user_id")),
            Settlement.group_id == int(group_id)
        )
    ).scalar()  # `scalar()` gives the single value

    # If no amount has been paid, set to 0
    total_paid_by_user = total_paid_by_user or 0

    grouped_data = defaultdict(list)

    # Process each transaction in the result
    for row in result:
        # Extract the relevant fields
        expense_id = row.expense_id
        group_id = row.group_id
        user_id = row.id
        description = row.description
        amount = row.amount
        paid_by = row.paid_by
        payee_first_name = row.paid_by_first_name.title()
        payee_last_name = row.paid_by_last_name.title() + " " if row.paid_by_last_name else ""
        expense_split_user_full_name = row.expense_split_first_name + " " + row.expense_split_last_name
        split_type = row.split_type
        created_by = row.created_by
        share = row.share
        created_at = row.created_at

        # Extract month and year for grouping
        month_key = created_at.strftime("%B %Y")
        create_date = created_at.strftime("%b %d")

        # Determine transaction type (lent or owe)
        transaction_type = "Receive" if paid_by == current_user.get("user_id") else "Pay"

        # If current user is not the one who paid, show the amount they paid
        amount_paid_by = (
            f"{payee_first_name.title()} {payee_last_name} paid ₹{amount}"
            if paid_by != current_user.get("user_id") else
            f"You paid ₹{amount}"
        )

        # Check if the expense already exists for that month
        expense_exists = False
        for expense in grouped_data[month_key]:
            if expense["expense_id"] == expense_id:
                expense_exists = True
                # Adjust the share if paid_by is the current user
                if paid_by == current_user.get("user_id"):
                    # Subtract the user's share from the total amount
                    adjusted_share = amount - share
                    expense["share"] = f"₹ {str(adjusted_share)}"
                    expense["users"].append(expense_split_user_full_name)
                else:
                    if user_id == current_user.get('user_id'):
                        expense["share"] = f"₹ {str(share)}"

        # If expense does not exist, add it
        if not expense_exists:
            grouped_data[month_key].append({
                "group_id": group_id,
                "expense_id": expense_id,
                "transaction_date": create_date if len(create_date) > 1 else f"0{create_date}",
                "description": description,
                "users": [expense_split_user_full_name],
                "amount_paid_by": amount_paid_by,
                "transaction_type": transaction_type,
                "share": f"₹ {str(share)}",
                "split_type": split_type,
                "created_by": created_by
            })

    return templates.TemplateResponse('view-group.html', context={'request': request, "group_id": group_id, "data_list": grouped_data, "total_paid_by_user": total_paid_by_user})

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
    print(form_data)
    expense_description = form_data.get("expense_description")
    expense_amount = float(form_data.get("expense_amount")) if form_data.get("expense_amount") else 0
    expense_paid_by = form_data.get("expense_paid_by")
    expense_split_amoung = form_data.getlist("expense_split_amoung[]")
    expense_split_type = form_data.get("split_type")
    expense_date = form_data.get("expense_date")
    expense_ratios = form_data.getlist("expense_ratios[]")
    expense_exact_shares = form_data.getlist("expense_exact_shares[]")
    current_user_id = current_user.get("user_id")

    if expense_split_type == "ratio" and not expense_ratios:
        raise HTTPException(status_code=400, detail="Ratios must be provided when split type is 'ratio'.")

    if expense_split_type == "ratio":
        ratios = list(map(int, expense_ratios))
        if sum(ratios) != 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The sum of the ratios must equal 100. Current sum: {sum(ratios)}"
            )

    expense_ratio_per_user = {}
    if expense_split_type == "ratio":
        for user_id, ratio in zip(expense_split_amoung, expense_ratios):
            expense_ratio_per_user[int(user_id)] = float(ratio)
    elif expense_split_type == "exact" and expense_exact_shares:
        for user_id, share in zip(expense_split_amoung, expense_exact_shares):
            expense_ratio_per_user[int(user_id)] = float(share)

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
        if expense_split_type != "equal":
            raise HTTPException(
        status_code=400,
        detail="When no users are selected for splitting the expense, a valid split type (either 'ratio' or 'exact') must be used, and the corresponding data must be provided."
    )

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
        
        elif expense_split_type == "ratio":
            ratio = expense_ratio_per_user[int(member)]
            member_share = (expense_amount * ratio) / 100  # Proportional to the ratio
            new_expense_split = ExpenseSplit(
                expense_id = new_expense.expense_id,
                user_id = int(member),
                share = member_share,
                ratio = ratio  # Storing the ratio here
            )
            db.add(new_expense_split)
            db.commit()

        elif expense_split_type == "exact":
            # For 'exact' split, use the exact share per user
            member_share = expense_ratio_per_user[int(member)]
            new_expense_split = ExpenseSplit(
                expense_id = new_expense.expense_id,
                user_id = int(member),
                share = member_share,
                ratio = 0  # Not used for 'exact' split
            )
            db.add(new_expense_split)
            db.commit()
        

    response = RedirectResponse(url=f"/view-group/{group_id}", status_code=status.HTTP_303_SEE_OTHER)
    return response

@app.get("/add-member/{group_id}")
async def get_add_meber(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    # Get all friend user IDs as a flat list
    group_members_ids = [group_member.user_id for group_member in db.query(GroupMember.user_id).filter(GroupMember.group_id == group_id).all()]

    current_user_id = current_user.get('user_id')

    # Query to get friends in the group who are not already in all_friends
    friends_list = (
        db.query(Friends.user_id, User.first_name, User.last_name)
        .join(Friends, Friends.user_id == User.id)
        .filter(
            and_(
                Friends.user_id.not_in(group_members_ids),
                Friends.friend_id == current_user_id
            )
        )
        .all()
    )

    return templates.TemplateResponse('add-member.html', context={'request': request, "current_user": current_user, "group_id": group_id, "friends": friends_list})

@app.post("/add-member/{group_id}")
async def add_member(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

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

@app.get("/view-members/{group_id}")
async def view_members(request: Request, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    group_members = db.query(GroupMember.user_id, User.first_name, User.last_name).join(GroupMember, GroupMember.user_id == User.id).filter(GroupMember.group_id == group_id).all()

    return templates.TemplateResponse('view-members.html', context={'request': request, "current_user": current_user, "group_id": group_id, "members": group_members})

@app.get("/remove-members/{group_id}/{user_id}")
async def view_members(request: Request, user_id: int, group_id: int, current_user= Depends(get_current_user), db: Session = Depends(get_db)):

    db.query(GroupMember).filter(
        and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
        ).delete()
    
    db.commit()
    
    group_members = db.query(GroupMember.user_id, User.first_name, User.last_name).join(GroupMember, GroupMember.user_id == User.id).filter(GroupMember.group_id == group_id).all()

    return templates.TemplateResponse('view-members.html', context={'request': request, "current_user": current_user, "group_id": group_id, "members": group_members})


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

@app.get("/accounts")
async def get_accounts(request: Request, current_user=Depends(get_current_user), db:Session = Depends(get_db)):

    user = db.query(User).filter(User.id == current_user.get("user_id")).first()
    
    friend_request_list = (
        db.query(FriendRequests.friend_request_id, User.first_name, User.last_name)
        .join(FriendRequests, FriendRequests.friend_request_id == User.id)
        .filter(FriendRequests.user_id == current_user.get("user_id"))
        .all()
    )

    return templates.TemplateResponse("accounts.html", {"request": request, "user": user, 'total_friend_requests': len(friend_request_list)})

@app.get("/view-report/{group_id}")
async def view_report(request: Request, group_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):

    # Fetch the current user
    user_id = current_user.get('user_id')

    # Fetch all expenses for the group where the current user is involved (either as 'paid_by' or in 'ExpenseSplit')
    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()

    # Fetch all expense splits for the group
    expense_splits = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id.in_([expense.expense_id for expense in expenses])).all()

    # Fetch all users and group members
    users = db.query(User).all()
    group_members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()

    # Create a PDF canvas
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4  # Page size (A4 format)
    margin = 50  # Left margin

    # Function to handle text overflow and page changes
    def add_text_line(pdf, text, x, y):
        pdf.drawString(x, y, text)
        return y - 16  # Update y position after writing a line

    # Add Title
    y_position = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    y_position = add_text_line(pdf, f"Expense Report for: Dec 2024", 180, y_position)
    y_position = add_text_line(pdf, "", 180, y_position)

    # Group Details Section
    pdf.setFont("Helvetica", 12)
    y_position = add_text_line(pdf, f"Group Name: Aarcity 1601", margin, y_position)
    y_position = add_text_line(pdf, f"Members:", margin, y_position)
    for member in group_members:
        member_user = db.query(User).filter(User.id == member.user_id).first()
        y_position = add_text_line(pdf, f"• {member_user.first_name} {member_user.last_name}", margin, y_position)
    y_position = add_text_line(pdf, f"Date: 25th Nov 2024 - 25th Dec 2024", margin, y_position)

    # Summary Boxes
    pdf.setFont("Helvetica-Bold", 12)

    # pdf.rect(50, y_position - 120, 150, 120, stroke=1, fill=0)
    # pdf.drawString(60, y_position - 20, f"Total Spent   : 260000")
    # pdf.drawString(60, y_position - 40, f"Actual Spent : 139865")

    # pdf.rect(210, y_position - 120, 165, 120, stroke=1, fill=0)
    # pdf.drawString(220, y_position - 20, f"Owe:")
    # pdf.drawString(220, y_position - 40, f"Ankit: 123456")
    # pdf.drawString(220, y_position - 60, f"Gunjan: 123456")
    # pdf.drawString(220, y_position - 80, f"Sudhir: 123456")
    # pdf.drawString(220, y_position - 100, f"Yash: 123456")

    # pdf.rect(385, y_position - 120, 165, 120, stroke=1, fill=0)
    # pdf.drawString(395, y_position - 20, f"Give:")
    # pdf.drawString(395, y_position - 40, f"Ankit: 123456")
    # pdf.drawString(395, y_position - 60, f"Gunjan: 123456")
    # pdf.drawString(395, y_position - 80, f"Sudhir: 123456")
    # pdf.drawString(395, y_position - 100, f"Yash: 123456")
    # Draw the summary box for total spent and owed amounts
    # Initialize data for tracking user expenses and calculations
    total_spent_by_user = 0
    user_expense_data = {user.id: {"pay": 0, "owed": 0, "share": 0} for user in users}

    # Track payments and splits for the current user
    for expense in expenses:
        # Check if the current user paid this expense
        if expense.paid_by == user_id:
            total_spent_by_user += expense.amount
        
        # Loop through splits to calculate how much each user owes or needs to pay
        for split in expense_splits:
            if split.expense_id == expense.expense_id:
                if split.user_id == user_id:
                    user_expense_data[user_id]["share"] += split.share
                    # If the user is the payer, they have already paid, so they should receive money from others
                    if expense.paid_by != user_id:
                        user_expense_data[expense.paid_by]["pay"] += split.share
                else:
                    # If the user is not the one who split the expense, check how much they owe
                    if expense.paid_by == user_id:
                        user_expense_data[split.user_id]["owed"] += split.share
                    else:
                        user_expense_data[split.user_id]["share"] += split.share

    actual_spent = user_expense_data[user_id]["share"]
            
    # Draw the summary box for total spent and owed amounts
    pdf.rect(50, y_position - 120, 150, 120, stroke=1, fill=0)
    pdf.drawString(60, y_position - 20, f"Total Spent: {total_spent_by_user:.2f}")
    pdf.drawString(60, y_position - 40, f"Actual Spent: {actual_spent:.2f}")

    # Draw the summary box for 'Give' and 'Receive' calculations
    pdf.rect(210, y_position - 120, 165, 120, stroke=1, fill=0)
    pdf.drawString(220, y_position - 20, f"Pay:")
    
    height = 0
    # Show how much the current user needs to give to others
    for member in group_members:
        member_user = db.query(User).filter(User.id == member.user_id).first()
        if member_user.id != user_id:  # Don't include yourself in this section
            share = user_expense_data[member_user.id]["pay"]
            pdf.drawString(220, y_position - 40 - height, f"{member_user.first_name}: {share:.2f}")
            height += 20

    pdf.rect(385, y_position - 120, 165, 120, stroke=1, fill=0)
    pdf.drawString(395, y_position - 20, f"Receive:")

    height = 0
    # Show how much others owe to the current user
    for member in group_members:
        member_user = db.query(User).filter(User.id == member.user_id).first()
        if member_user.id != user_id:  # Don't include yourself in this section
            owed = user_expense_data[member_user.id]["owed"]
            pdf.drawString(395, y_position - 40 - height, f"{member_user.first_name}: {owed:.2f}")
            height += 20

    # Adjust the position for the Description section
    y_position -= 50  # Space before the next section
    pdf.setFont("Helvetica", 12)
    y_position = add_text_line(pdf, "Expenses Involving You:", margin, y_position - 95)

    y_position -= 10
    # Draw the table header with new headers
    table_header = ["#", "Description", "Amount", "Paid By", "Split Type", "Share"]
    pdf.setFont("Helvetica-Bold", 12)
    col_widths = [50, 180, 70, 70, 70, 60]  # Adjusted widths for each column
    x_pos = margin
    for i, header in enumerate(table_header):
        pdf.drawString(x_pos, y_position, header)
        x_pos += col_widths[i]

    y_position -= 20  # Move below header row

    try:
        [share for share in db.query(ExpenseSplit.share).filter(
            and_(
                ExpenseSplit.expense_id == expense.expense_id,
                ExpenseSplit.user_id == user_id
            )
            ).first()][0]
    except:
        print(f"No expense avalaible for the user {current_user.get('first_name')} {current_user.get('last_name')}")
        # Save the PDF to the buffer
        pdf.save()

        buffer.seek(0)

        # Return the PDF as a response
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=expense_report.pdf"}
        )

    # Add Expenses
    pdf.setFont("Helvetica", 10)
    for expense in expenses:
        if y_position < 100:  # Check if the page is full and needs a new one
            pdf.showPage()  # Add a new page
            y_position = height - 50  # Reset y_position for the new page
            # Re-draw table header in the new page
            x_pos = margin
            for i, header in enumerate(table_header):
                pdf.drawString(x_pos, y_position, header)
                x_pos += col_widths[i]
            y_position -= 20  # Move below header row again

        # Expense row data
        y_position = add_text_line(pdf, str(expense.expense_id), margin, y_position)
        y_position = add_text_line(pdf, expense.description, margin + col_widths[0], y_position + 16)
        y_position = add_text_line(pdf, f"{expense.amount:.2f}", margin + col_widths[0] + col_widths[1], y_position + 16)
        
        paid_by_user = db.query(User).filter(User.id == expense.paid_by).first()
        y_position = add_text_line(pdf, f"{paid_by_user.first_name}", margin + col_widths[0] + col_widths[1] + col_widths[2], y_position + 16)
        
        # Split Type
        y_position = add_text_line(pdf, expense.split_type.capitalize(), margin + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], y_position + 16)
        
        # Add the expense split data for this expense
        share = [share for share in db.query(ExpenseSplit.share).filter(
            and_(
                ExpenseSplit.expense_id == expense.expense_id,
                ExpenseSplit.user_id == user_id
            )
            ).first()][0]
        y_position = add_text_line(pdf, f"{share:.2f}", margin + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], y_position + 16)


    # Save the PDF to the buffer
    pdf.save()

    buffer.seek(0)

    # Return the PDF as a response
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=expense_report.pdf"}
    )