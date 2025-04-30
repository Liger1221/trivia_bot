import json
import logging
import os
import random
from typing import Dict, List, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# User session storage
user_sessions = {}

# Maximum questions per round
MAX_QUESTIONS = 10

class TriviaSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.current_question = None
        self.score = 0
        self.questions_asked = 0
        self.category = None

def load_questions() -> Dict[str, List[Dict[str, Any]]]:
    """Load questions from the database.json file and organize them by category."""
    with open("database.json", "r") as file:
        data = json.load(file)
    
    # Organize questions by category
    questions_by_category = {}
    for question in data["questions"]:
        category = question["category"]
        if category not in questions_by_category:
            questions_by_category[category] = []
        questions_by_category[category].append(question)
    
    return questions_by_category

# Load questions at startup
questions_by_category = load_questions()
categories = list(questions_by_category.keys())

async def show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    """Show the category selection menu."""
    # Create category selection buttons
    keyboard = []
    for i in range(0, len(categories), 2):
        row = []
        for j in range(2):
            if i + j < len(categories):
                category = categories[i + j]
                # Capitalize the first letter of each category
                display_name = category.capitalize()
                row.append(InlineKeyboardButton(display_name, callback_data=f"category_{category}"))
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "Welcome to the Trivia Quiz Bot! Please select a category:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=message_text,
            reply_markup=reply_markup
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    
    # Create a new session for the user
    user_sessions[user_id] = TriviaSession(user_id)
    
    await show_category_menu(update)

async def send_question(update: Update, user_id: int) -> None:
    """Send a random question from the selected category."""
    session = user_sessions[user_id]
    
    # Check if we've reached the maximum number of questions
    if session.questions_asked >= MAX_QUESTIONS:
        # Show final score and option to choose a new category
        keyboard = [[InlineKeyboardButton("Choose New Category", callback_data="new_category")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        final_message = (
            f"🎮 Quiz Complete! 🎮\n\n"
            f"You've completed {MAX_QUESTIONS} questions in the {session.category.capitalize()} category.\n\n"
            f"Final Score: {session.score}/{MAX_QUESTIONS}\n\n"
            f"Select 'Choose New Category' to play again!"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=final_message,
                reply_markup=reply_markup
            )
        return
    
    # Get a random question from the selected category
    category_questions = questions_by_category[session.category]
    session.current_question = random.choice(category_questions)
    
    # Create option buttons
    keyboard = []
    for i in range(0, len(session.current_question["options"]), 2):
        row = []
        for j in range(2):
            if i + j < len(session.current_question["options"]):
                option = session.current_question["options"][i + j]
                row.append(InlineKeyboardButton(option, callback_data=f"answer_{option}"))
        keyboard.append(row)
    
    # Add "Back to Menu" button
    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the question
    question_text = (
        f"Category: {session.category.capitalize()}\n"
        f"Question {session.questions_asked + 1}/{MAX_QUESTIONS}:\n\n"
        f"{session.current_question['question']}"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=question_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=question_text,
            reply_markup=reply_markup
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks."""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Make sure the user has a session
    if user_id not in user_sessions:
        user_sessions[user_id] = TriviaSession(user_id)
    
    session = user_sessions[user_id]
    
    await query.answer()  # Acknowledge the button click
    
    if query.data.startswith("category_"):
        # User selected a category
        category = query.data.replace("category_", "")
        session.category = category
        session.score = 0
        session.questions_asked = 0
        
        await query.edit_message_text(f"You selected: {category.capitalize()}\n\nLet's start the quiz!")
        await send_question(update, user_id)
    
    elif query.data.startswith("answer_"):
        # User answered a question
        selected_answer = query.data.replace("answer_", "")
        correct_answer = session.current_question["answer"]
        
        session.questions_asked += 1
        
        if selected_answer == correct_answer:
            session.score += 1
            result_text = f"✅ Correct! The answer is: {correct_answer}\n\nYour score: {session.score}/{session.questions_asked}"
        else:
            result_text = f"❌ Wrong! The correct answer is: {correct_answer}\n\nYour score: {session.score}/{session.questions_asked}"
        
        # Show result and next question button
        keyboard = [
            [InlineKeyboardButton("Next Question", callback_data="next_question")],
            [InlineKeyboardButton("Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=result_text,
            reply_markup=reply_markup
        )
    
    elif query.data == "next_question":
        # Send the next question
        await send_question(update, user_id)
    
    elif query.data == "back_to_menu" or query.data == "new_category":
        # Return to category selection menu
        await show_category_menu(update)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "Welcome to the Trivia Quiz Bot!\n\n"
        "Commands:\n"
        "/start - Start the quiz and select a category\n"
        "/help - Show this help message\n\n"
        "How to play:\n"
        "1. Select a category\n"
        "2. Answer the multiple-choice questions\n"
        "3. See your score and continue playing\n"
        "4. After 10 questions, you'll see your final score\n"
        "5. You can return to the category menu at any time\n\n"
        "Have fun!"
    )
    await update.message.reply_text(help_text)

def main() -> None:
    """Start the bot."""
    # Get the bot token from environment variable
    token = "8138955854:AAHyIiKwbBcSzPiMM0KvCCK-69kiaJTBdyU"
    if not token:
        logger.error("No BOT_TOKEN environment variable found!")
        return
    
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
